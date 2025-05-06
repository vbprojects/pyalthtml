from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
from pathlib import Path
from .compiler import AlthtmlCompiler

def trigger_recompile(write_pairs, header_files, compiler):
    for h in header_files:
        compiler.compile(open(h, "r").read())
    for (k, v) in write_pairs.items():
        with open(v, "w+") as f:
            f.write(compiler.compile(open(k, "r").read()))

class ChangeHandler(FileSystemEventHandler):
    def __init__(self, files_to_watch, write_pairs = None, header_files = None):
        self.files_to_watch = [x.resolve() for x in files_to_watch] # Set of absolute paths (headers + sources)
        self.write_pairs = write_pairs       # Dict {abs_src: abs_dst}
        self.header_files = header_files     # Set of absolute paths (headers)
        self.compiler = AlthtmlCompiler()
        print("Handler initialized. Monitoring for changes...")

    def on_modified(self, event):
        if event.is_directory:
            return

        # Resolve path and check if it's one we care about
        src_path_abs = Path(event.src_path).resolve()
        if src_path_abs in self.files_to_watch:
            print(f"\nDetected modification in: {src_path_abs}")
            # Pass the necessary path collections to the trigger function
            trigger_recompile(self.write_pairs, self.header_files, self.compiler)
        # else: file modified is not in our watch list, ignore.

    # on_created, on_deleted can be added similarly if needed


def run_watcher(no_write_paths, write_pairs, watch_paths):
    """Sets up and runs the watchdog observer."""
    files_to_watch = set(write_pairs.keys())
    dirs_to_watch = {p.parent for p in files_to_watch | no_write_paths | watch_paths}
    
    if not dirs_to_watch:
         print("Error: No valid directories provided to watch.")
         return
    if not files_to_watch:
         print("Warning: No specific files provided to monitor within directories.")
         # Decide if you want to proceed or exit if files_to_watch is empty
    
    
    
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    event_handler = ChangeHandler(files_to_watch | no_write_paths | watch_paths, write_pairs=write_pairs, header_files=no_write_paths, watch_files=watch_paths)
    observer = Observer()

    scheduled_count = 0
    for dir_path in dirs_to_watch:
        if not isinstance(dir_path, Path):
             print(f"Error: Item in dirs_to_watch is not a Path object: {dir_path}")
             continue
        if not dir_path.is_dir():
             print(f"Warning: Directory '{dir_path}' does not exist. Cannot watch.")
             continue

        # Schedule monitoring for the directory.
        # recursive=False means watchdog only looks for events directly
        # within this directory, not subdirectories.
        observer.schedule(event_handler, str(dir_path), recursive=False)
        scheduled_count += 1
        print(f"Scheduled watcher for directory: {dir_path}")

    if scheduled_count == 0:
         print("Error: No watchers were successfully scheduled. Exiting.")
         return

    observer.start()
    print(f"\nWatching for file changes in {scheduled_count} director{'y' if scheduled_count == 1 else 'ies'}. Press Ctrl+C to stop.")

    try:
        while observer.is_alive():
            observer.join(timeout=1) # Wait for observer thread, check status periodically
    except KeyboardInterrupt:
        print("\nStopping watcher (Ctrl+C pressed)...")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        if observer.is_alive():
            observer.stop()
            print("Observer stop signal sent.")
        # Wait for the observer thread to fully finish shutting down
        observer.join()
        print("Watcher stopped completely.")