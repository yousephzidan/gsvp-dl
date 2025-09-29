import asyncio
import aiohttp
from rich import print

from gsvpd.core import fetch_panos
from gsvpd.my_utils import (
    open_dataset,
    parse_args,
    timer
)

async def main(args) -> tuple[int, int, str]:
    dataset = open_dataset(args.dataset)

    if limit:= args.limit: 
        dataset = dataset[:limit]

    sem_pano = asyncio.Semaphore(args.max_pano)
    sem_tile = asyncio.Semaphore(args.max_tile)

    connector = aiohttp.TCPConnector(limit=args.conn_limit, limit_per_host=args.conn_limit_perh)

    return await fetch_panos(sem_pano, sem_tile, connector, args.workers, args.zoom, dataset, args.output)


if __name__ == "__main__":
    try:
        args = parse_args() 

        with timer() as t:
            total_panos, successful_panos, output_dir = asyncio.run(main(args))

        print(f"\n[gray]{'-' * 85}[/]")
        print(f"\n[orange1]| Processed [green]{successful_panos}/{total_panos}[/] panos in [green]{t.time_elapsed}[/][/]")
        print(f"[orange1]| Saved at [green]{output_dir}[/][/]\n")
    except Exception as error:
        print(f"[red][MAIN] Error: {error}[/]")
    except KeyboardInterrupt:
        print("[red]Keyboard Interrupted[/]")
