import argparse
import subprocess
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
#print(script_dir)
def run_gem5(args, output_file=os.path.join(script_dir, "output.txt")):
    #print(output_file)
    cmd = [
        "./build/NULL/gem5.debug", "configs/example/garnet_synth_traffic.py",
        "--num-cpus", str(args.num_cpus),
        "--num-dirs", str(args.num_dirs),
        "--network", args.network,
        "--topology", args.topology,
        "--mesh-rows", str(args.mesh_rows),
        "--router-latency", str(args.router_latency),
        "--link-latency", str(args.link_latency),
        "--vcs-per-vnet", str(args.vcs_per_vnet),
        "--link-width-bits", str(args.link_width_bits),
        "--sim-cycles", str(args.sim_cycles),
        "--synthetic", args.synthetic,
        "--injectionrate", str(args.injectionrate),
        "--single-sender-id", str(args.single_sender_id),
        "--single-dest-id", str(args.single_dest_id),
        "--num-packets-max", str(args.num_packets_max),
        "--inj-vnet", str(args.inj_vnet),
    ]
    with open(output_file, "w") as f:
        subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)

def parse_and_process(input_file=os.path.join(script_dir, "output.txt"), output_file=os.path.join(script_dir, "processed.txt")):
    with open(input_file) as f:
        logs = [line.strip() for line in f if line.startswith("###")]

    parsed = []
    for line in logs:
        parts = line.split()
        tick = int(parts[1])
        event = parts[2]
        global_id = int(parts[3])
        parsed.append((global_id, tick, line, parts))

    parsed.sort(key=lambda x: (x[0], x[1]))

    result_lines = []
    n = len(parsed)
    for i, (gid, tick, line, parts) in enumerate(parsed):
        result_lines.append(line)

        # 找下一个相同 global_id 的事件
        next_tick = None
        for j in range(i + 1, n):
            gid2, tick2, _, parts2 = parsed[j]
            if gid2 == gid:
                next_tick = tick2
                break

        if parts[2] == "ST":
            # 插入 DT，直到下一个 RR
            rr_tick = None
            for j in range(i + 1, n):
                gid2, tick2, _, parts2 = parsed[j]
                if gid2 == gid and parts2[2] == "RR":
                    rr_tick = tick2
                    break

            if rr_tick:
                new_tick = tick + 250
                while new_tick < rr_tick:
                    new_parts = parts.copy()
                    new_parts[1] = str(new_tick)
                    new_parts[2] = "DT"
                    result_lines.append(" ".join(new_parts))
                    new_tick += 250

        elif parts[2] == "RR":
            # 插入 DR，直到下一个事件
            if next_tick:
                new_tick = tick + 250
                while new_tick < next_tick:
                    new_parts = parts.copy()
                    new_parts[1] = str(new_tick)
                    new_parts[2] = "RR"
                    result_lines.append(" ".join(new_parts))
                    new_tick += 250

    with open(output_file, "w") as f:
        f.write("\n".join(result_lines) + "\n")

def get_arg_parser():
    parser = argparse.ArgumentParser(description="Run Garnet gem5 and process logs")
    # System config
    parser.add_argument("--num-cpus", type=int, default=16)
    parser.add_argument("--num-dirs", type=int, default=16)
    parser.add_argument("--network", type=str, default="garnet")
    parser.add_argument("--topology", type=str, default="Mesh_XY")
    parser.add_argument("--mesh-rows", type=int, default=4)
    # Network config
    parser.add_argument("--router-latency", type=int, default=1)
    parser.add_argument("--link-latency", type=int, default=1)
    parser.add_argument("--vcs-per-vnet", type=int, default=4)
    parser.add_argument("--link-width-bits", type=int, default=128)
    # Traffic
    parser.add_argument("--sim-cycles", type=int, default=10000)
    parser.add_argument("--synthetic", type=str, default="uniform_random")
    parser.add_argument("--injectionrate", type=float, default=1.0)
    parser.add_argument("--single-sender-id", type=int, default=5)
    parser.add_argument("--single-dest-id", type=int, default=7)
    parser.add_argument("--num-packets-max", type=int, default=1)
    parser.add_argument("--inj-vnet", type=int, default=0)

    return parser

if __name__ == "__main__":
    parser = get_arg_parser()
    args = parser.parse_args()

    # Step 1: Run gem5 with args
    run_gem5(args)

    # Step 2: Process logs
    parse_and_process()