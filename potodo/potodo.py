#!/usr/bin/env python3

import argparse
import os
import json
import statistics

from typing import Tuple, Mapping, Sequence, List
from pathlib import Path

from potodo import __version__
from potodo._github import get_reservation_list
from potodo._po_file import PoFileStats, get_po_files_from_repo

# TODO: Sort the functions (maybe in different files ?


def initialize_arguments(
    above: int, below: int, offline: bool, hide_reserved: bool, repo_path: str
) -> Tuple[int, int, Mapping[str, str]]:
    """Will initialize the arguments as necessary
    """
    if not above:
        # If above isn't specified, then print all files above 0% (all of them)
        above = 0
    if not below:
        # If below isn't specified, then print all files below 100% (all of them)
        below = 100

    if above and below:
        if below < above:
            # If above and below are specified and that below is superior to above,
            # raise an error
            raise ValueError("Below must be inferior to above")

    if not offline and not hide_reserved:
        # If the reservations are to be displayed, then get them
        issue_reservations = get_reservation_list(repo_path)
    else:
        # Otherwise, an empty list will do the trick
        issue_reservations = {}
    return above, below, issue_reservations


def print_dir_stats(
    directory_name: str,
    buffer: Sequence[str],
    folder_stats: Sequence[int],
    printed_list: Sequence[bool],
) -> None:
    """This function prints the directory name, its stats and the buffer
    """
    if True in printed_list:
        # If at least one of the files isn't done then print the
        # folder stats and file(s) Each time a file is went over True
        # or False is placed in the printed_list list.  If False is
        # placed it means it doesnt need to be printed
        print(f"\n\n# {directory_name} ({statistics.mean(folder_stats):.2f}% done)\n")
        print("\n".join(buffer))


def add_dir_stats(
    directory_name: str, buffer: list, folder_stats: list, printed_list: list, all_stats: list
):
    """Appends directory name, its stats and the buffer to stats
    """
    if any(printed_list):
        all_stats.append(dict(name=f"{directory_name}/",
                              pc_translated=float(f"{statistics.mean(folder_stats):.2f}"),
                              files=buffer))


def exec_potodo(
    path: str,
    above: int,
    below: int,
    fuzzy: bool,
    offline: bool,
    hide_reserved: bool,
    counts: bool,
    json_format: bool,
):
    """
    Will run everything based on the given parameters

    :param path: The path to search into
    :param above: The above threshold
    :param below: The below threshold
    :param fuzzy: Should only fuzzies be printed
    :param offline: Will not connect to internet
    :param hide_reserved: Will not show the reserved files
    :param counts: Render list with counts not percentage
    :param json_format: Format output as JSON.
    """

    # Initialize the arguments
    above, below, issue_reservations = initialize_arguments(
        above, below, offline, hide_reserved, path
    )

    # Get a dict with the directory name and all po files.
    po_files_and_dirs = get_po_files_from_repo(path)

    dir_stats: list = []
    for directory_name, po_files in sorted(po_files_and_dirs.items()):
        # For each directory and files in this directory
        buffer: List[str] = []
        folder_stats: List[int] = []
        printed_list: List[bool] = []

        for po_file in sorted(po_files):
            # For each file in those files from that directory
            if not fuzzy or po_file.fuzzy_entries:
                buffer_add(
                    buffer,
                    folder_stats,
                    printed_list,
                    po_file,
                    issue_reservations,
                    above,
                    below,
                    counts,
                    json_format
                )

        # Once all files have been processed, print the dir and the files
        # or store them into a dict to print them once all directories have
        # been processed.
        if json_format:
            add_dir_stats(directory_name, buffer, folder_stats, printed_list, dir_stats)
        else:
            print_dir_stats(directory_name, buffer, folder_stats, printed_list)

    if json_format:
        print(json.dumps(dir_stats, indent=4, separators=(',', ': '), sort_keys=False))


def buffer_add(
    buffer: list,
    folder_stats: List[int],
    printed_list: List[bool],
    po_file_stats: PoFileStats,
    issue_reservations: Mapping[str, str],
    above: int,
    below: int,
    counts: bool,
    json_format: bool,
) -> None:
    """Will add to the buffer the information to print about the file is
    the file isn't translated entirely or above or below requested
    values.
    """
    # If the file is completely translated,
    # or is translated below what's requested
    # or is translated above what's requested
    if po_file_stats.percent_translated == 100 or \
            po_file_stats.percent_translated < above or \
            po_file_stats.percent_translated > below:

        # add the percentage of the file to the stats of the folder
        folder_stats.append(po_file_stats.percent_translated)

        if not json_format:
            # don't print that file
            printed_list.append(False)

        # return without adding anything to the buffer
        return

    # nb of fuzzies in the file IF there are some fuzzies in the file
    fuzzy_nb = po_file_stats.fuzzy_nb if po_file_stats.fuzzy_entries else 0
    # number of entries translated
    translated_nb = po_file_stats.translated_nb
    # file size
    po_file_size = po_file_stats.po_file_size
    # percentage of the file already translated
    percent_translated = po_file_stats.percent_translated
    # `reserved by` if the file is reserved unless the offline/hide_reservation are enabled
    reserved_by = issue_reservations.get(po_file_stats.filename_dir.lower(), None)

    if json_format:
        # the order of the keys is the display order
        desc = dict(name=f"{po_file_stats.directory}/{po_file_stats.filename.strip('.po')}",
                    path=str(po_file_stats.path), entries=po_file_size, fuzzies=fuzzy_nb,
                    translated=translated_nb, pc_translated=percent_translated, reserved_by=reserved_by)

    else:
        desc = f"- {po_file_stats.filename:<30} "  # The filename

        if counts:
            missing = len(po_file_stats.fuzzy_entries) + len(po_file_stats.untranslated_entries)
            desc += f"{missing:3d} to do"
            desc += f", including {fuzzy_nb} fuzzies." if fuzzy_nb else ""

        else:
            desc += f"{translated_nb:3d} / {po_file_size:3d} "
            desc += f"({percent_translated:5.1f}% translated)"
            desc += f", {fuzzy_nb} fuzzy" if fuzzy_nb else ""

        if reserved_by is not None:
            desc += f", réservé par {reserved_by}"

    buffer.append(desc)

    # Add the percent translated to the folder statistics
    folder_stats.append(po_file_stats.percent_translated)
    # Indicate to print the file
    printed_list.append(True)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="potodo",
        description="Sequence and prettify the po files left to translate",
    )

    parser.add_argument(
        "-p",
        "--path",
        type=Path,
        help="Execute Potodo in the given path"
    )

    parser.add_argument(
        "-a",
        "--above",
        type=int,
        help="Will list all TODOs ABOVE given INT%% completion",
    )

    parser.add_argument(
        "-b",
        "--below",
        type=int,
        help="Will list all TODOs BELOW given INT%% completion",
    )

    parser.add_argument(
        "-f",
        "--fuzzy",
        action="store_true",
        help="Will only print files marked as fuzzys",
    )

    parser.add_argument(
        "-o",
        "--offline",
        action="store_true",
        help="Will not do any fetch to GitHub/online if given",
    )

    parser.add_argument(
        "-n",
        "--no-reserved",
        action="store_true",
        help="Will not print the info about reserved files",
    )

    parser.add_argument(
        "-c",
        "--counts",
        action="store_true",
        help="Render list with the count of remaining entries "
        "(translate or review) rather than percentage done",
    )

    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Format output as JSON.",
    )

    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__
    )

    args = parser.parse_args()
    # If no path is specified, then use the current path
    if args.path:
        path = str(args.path)
    else:
        path = os.getcwd()

    exec_potodo(
        path,
        args.above,
        args.below,
        args.fuzzy,
        args.offline,
        args.no_reserved,
        args.counts,
        args.json,
    )
