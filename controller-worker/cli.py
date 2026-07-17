import argparse
import asyncio
from engine import run_load_test

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--users", type=int, default=25)
    parser.add_argument("--duration", type=int, default=10)
    args = parser.parse_args()

    stats = asyncio.run(run_load_test(args.users, args.url, args.duration))
    print(stats)

if __name__ == "__main__":
    main()