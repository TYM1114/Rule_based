import time
import csv
import os
import sys
import datetime
import yaml

import rb_solver
import gen_sequence
import data_generator

class DualLogger:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.log_file = open(filepath, "w", encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

class YardSimulationController:
    def __init__(self, config_path="config.yaml"):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load config.yaml: {e}")

        self.mode = self.config['simulation']['mode']
        self.target_run_id = str(self.config['simulation']['target_run_id'])
        self.active_run_id = self.target_run_id
        
        self.data_gen = data_generator.YardDataGenerator()
        self.seq_optimizer = gen_sequence.SequenceOptimizer()
        
        self.yard_config = {}
        self.boxes = []
        self.job_sequence = []
        self.sku_map = {}
        self.target_dest_map = {}
        self.selection_run_id_info = {}

        # Logging setup
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_base_dir = self.config.get('logging', {}).get('output_dir', 'logs')
        self.log_dir = os.path.join(log_base_dir, self.timestamp)
        os.makedirs(self.log_dir, exist_ok=True)
        
        execution_log_path = os.path.join(self.log_dir, 'execution_log.txt')
        sys.stdout = DualLogger(execution_log_path)
        
        print("==================================================")
        print(f"RB SOLVER SIMULATION PIPELINE STARTED")
        print(f"Time  : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Log Dir: {self.log_dir}")
        print("==================================================")

    def optimize_sequence(self, num_batches=10, start_id=None):
        print("\n[Phase 1] Sequence Optimization")
        out_file, reseq_id = self.seq_optimizer.generate(num_batches, start_id or self.target_run_id)
        if not reseq_id:
            raise RuntimeError("Sequence generation failed.")
        self.active_run_id = reseq_id
        print(f"Optimized Sequence generated: {self.active_run_id}")

    def prepare_data(self):
        print(f"\n[Phase 2] Data Preparation (Mode: {self.mode})")
        if self.mode == "random":
            self.yard_config, self.boxes, self.job_sequence, self.sku_map, self.target_dest_map, self.selection_run_id_info = self.data_gen.generate_random(
                max_row=self.config['yard']['max_row'],
                max_bay=self.config['yard']['max_bay'],
                max_level=self.config['yard']['max_level'],
                total_boxes=self.config['random']['total_boxes'],
                mission_count=self.config['random']['mission_count'],
                workstation_count=self.config['yard']['workstation_count']
            )
        elif self.mode == "db":
            self.yard_config, self.boxes, self.job_sequence, self.sku_map, self.target_dest_map, self.selection_run_id_info = self.data_gen.generate_db(self.config, self.active_run_id, self.target_run_id)
        
        if not self.boxes or not self.job_sequence:
            raise RuntimeError("Data preparation failed: Empty boxes or job sequence.")
            
        print(f"Loaded {len(self.boxes)} boxes and {len(self.job_sequence)} targets.")

    def run_solver(self):
        print(f"\n[Phase 3] Running Rule-Based Solver")
        
        # Merge YAML config with specific RB Solver parameters
        full_config = self.yard_config.copy()
        full_config.update({
            'agv_count': self.config['solver']['agv_count'],
            'port_count': self.config['yard']['port_count'],
            'w_penalty_lookahead': self.config['solver']['w_penalty_lookahead'],
            't_travel': self.config['time']['t_travel'],
            't_handle': self.config['time']['t_handle'],
            't_process': self.config['time']['t_port_handle'],  # 對應舊的 t_process
            't_pick': self.config['time']['t_unit_process'],     # 對應舊的 t_pick
            'sim_start_epoch': self.config['time']['sim_start_epoch']
        })

        start_time = time.time()
        logs = rb_solver.run_rb_solver(
            full_config, 
            self.boxes, 
            self.job_sequence, 
            self.sku_map, 
            self.target_dest_map
        )
        duration = time.time() - start_time
        print(f"Solver finished in {duration:.2f} seconds.")
        return logs

    def export_results(self, logs):
        output_file = os.path.join(self.log_dir, 'output_missions_python.csv')
        counts = {"target": 0, "reshuffle": 0, "return": 0, "transfer": 0}
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "mission_no", "agv_id", "mission_type", "container_id", "related_target_id", 
                "src_pos", "dst_pos", "start_s", "end_s", "makespan", "duration_breakdown"
            ])
            
            epoch = self.config['time']['sim_start_epoch']
            for log in logs:
                if log.mission_type in counts: counts[log.mission_type] += 1
                s_pos = f"WS {abs(log.src[1])} (Port {log.src[2]})" if log.src[0] == -1 else f"({log.src[0]};{log.src[1]};{log.src[2]})"
                d_pos = f"WS {abs(log.dst[1])} (Port {log.dst[2]})" if log.dst[0] == -1 else f"({log.dst[0]};{log.dst[1]};{log.dst[2]})"

                writer.writerow([
                    log.mission_no, log.agv_id, log.mission_type, log.container_id-1, log.related_target_id-1,
                    s_pos, d_pos, log.start_time-epoch, log.end_time-epoch, log.makespan, log.duration_detail
                ])

        print(f"\n==================================================")
        print(f"SIMULATION SUMMARY")
        print(f"Total Missions: {len(logs)}")
        print(f"Target: {counts['target']} | Reshuffle: {counts['reshuffle']} | Return: {counts['return']} | Transfer: {counts['transfer']}")
        print(f"Final Makespan: {logs[-1].makespan if logs else 0:.2f}")
        print(f"Results saved to: {output_file}")
        print("==================================================")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Yard Simulation Pipeline")
    parser.add_argument("--mode", type=str, choices=["db", "random"], help="Simulation mode")
    parser.add_argument("--run_id", type=str, help="Target selection_run_id for DB mode")
    parser.add_argument("--multi", type=int, nargs="?", const=10, help="Run multi-batch optimization (count optional)")
    
    args, unknown = parser.parse_known_args()
    
    controller = YardSimulationController()
    
    # Override config if CLI args are provided
    if args.mode: controller.mode = args.mode
    if args.run_id: controller.target_run_id = args.run_id
    
    # Legacy and Multi support
    if args.multi is not None:
        start_id = unknown[0] if unknown else None
        controller.optimize_sequence(args.multi, start_id)
    elif len(sys.argv) > 1 and sys.argv[1] == "multi":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        start_id = sys.argv[3] if len(sys.argv) > 3 else None
        controller.optimize_sequence(count, start_id)
    elif len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        controller.active_run_id = sys.argv[1]

    controller.prepare_data()
    logs = controller.run_solver()
    controller.export_results(logs)

if __name__ == "__main__":
    main()
