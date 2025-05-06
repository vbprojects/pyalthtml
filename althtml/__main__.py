import yaml
from .watcher import run_watcher
import argparse
from pathlib import Path
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
                        prog='ProgramName',
                        description='What the program does',
                        epilog='Text at the bottom of help')
    parser.add_argument('config')
    args = parser.parse_args()
    cfg = yaml.safe_load(open(args.config, "r"))
    base_path = Path('.')
    no_write_paths = {header for header_str in cfg['headers'] for header in base_path.glob(header_str)} if 'headers' in cfg else set()
    watch_paths = {watch_path for watch_path_str in cfg['watch'] for watch_path in base_path.glob(watch_path_str)} if 'watch' in cfg else set()
    write_pairs = {Path(to_write['src']) : Path(to_write['dst']) for to_write in cfg['write']}
    run_watcher(no_write_paths, write_pairs, watch_paths)
