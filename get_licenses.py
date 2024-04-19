#!/usr/bin/env python3
# GET LICENSES.py
#   by Lut99
#
# Created:
#   19 Apr 2024, 14:43:51
# Last edited:
#   19 Apr 2024, 17:28:08
# Auto updated?
#   Yes
#
# Description:
#   Utility Python script that does what it says on the tin.
#   
#   For more information, see `README.md` in the root of the repository.
#

import argparse
import os
import requests
import sys
import time
import typing

import bs4


##### GLOBALS #####
# Keeps track of whether to print log-statements.
DEBUG = False





##### HELPER FUNCTIONS #####
def supports_color() -> bool:
    """
        Returns True if the running system's terminal supports color, and False
        otherwise.

        From: https://stackoverflow.com/a/22254892
    """
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or
                                                  'ANSICON' in os.environ)
    # isatty is not always implemented, #6223.
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform and is_a_tty

def log(text: str):
    """
        Logs something in debug mode, meaning it will only be shown if `--debug` is given.
    """

    global DEBUG
    if DEBUG:
        # Decide on colors
        colors = supports_color()
        start = "\033[90;1m" if colors else ""
        end = "\033[0m" if colors else ""
        print(f"{start}[DEBUG] {text}{end}")

def warn(text: str):
    """
        Logs something in warning mode, meaning it will have nice colours.
    """

    # Decide on colors
    colors = supports_color()
    accent = "\033[93;1m" if colors else ""
    bold = "\033[1m" if colors else ""
    end = "\033[0m" if colors else ""
    print(f"{accent}WARNING{end}{bold}: {text}{end}")

def error(text: str):
    """
        Logs something in error mode, meaning it will have nice colours.
    """

    # Decide on colors
    colors = supports_color()
    accent = "\033[91m" if colors else ""
    bold = "\033[1m" if colors else ""
    end = "\033[0m" if colors else ""
    print(f"{accent}ERROR{end}{bold}: {text}{end}")

def hackagify(package: str) -> str:
    """
        Given a Hackage package, returns a URL of the page to scrape.
    """

    return f"https://hackage.haskell.org/package/{package}"



def unique_licenses(pkgs: typing.Dict[str, typing.Any], hashes: typing.Dict[str, str] = {}, names_count: typing.Dict[str, int] = {}) -> typing.Dict[str, str]:
    """
        Finds the unique-by-hash licenses, resolving them to which licenses had the exact same body.

        # Returns
        A dictionary that maps package names to the potentially unique license identifiers of their license.
    """

    res = {}
    for pkg in pkgs:
        # Resolve the hash
        pkg = pkgs[pkg]
        license_hash = pkg.license_hash if pkg.license_hash is not None else f"{pkg.license}_unhashed"

        # Check if ours is unique
        if license_hash not in hashes:
            # Ensure there is a non-up-to-date count
            if pkg.license not in names_count:
                names_count[pkg.license] = 0

            # Generate unique name
            if names_count[pkg.license] == 0:
                name = pkg.license
            else:
                name = f"{pkg.license}({names_count[pkg.license]})"
            hashes[license_hash] = name

            # Update the count of unique variations of this license
            names_count[pkg.license] += 1

        # Add the mapping
        res[pkg.ident] = hashes[license_hash]
    return res





##### CLASSES #####
class License:
    """
        Represents a unique license that we found.
    """

    name: str
    type: str
    shash: str
    path: typing.Optional[str]
    packages: typing.List[str]

    def __init__(self, name, type, shash, path):
        self.name = name
        self.type = type
        self.shash = shash
        self.path = path
        self.packages = []



class Package:
    """
        Represents a scraped package.
    """

    ident: str
    short: str
    url: str
    license: str
    license_url: typing.Optional[str]
    license_hash: typing.Optional[str]

    def __init__(self, ident: str, short: str, url: str, license: str, license_url: typing.Optional[str], license_hash: typing.Optional[str]):
        """
            Constructor for the Package.

            # Arguments
            - `ident`: Some machine-friendly name of this package (e.g., `eflint`).
            - `short`: Some human-friendly short description of this package (e.g., `Simulation interpreter for FLINT policy descriptions`).
            - `url`: The URL which we scrape(d) to get this package.
            - `license`: The identifier for the license of this package.
            - `license_url`: The URL where the license may be found.
            - `license_hash`: The hash of the license itself.
        """

        self.ident = ident
        self.short = short
        self.url = url
        self.license = license
        self.license_url = license_url
        self.license_hash = license_hash

    def scrape(ident: str, url: str, download: typing.Optional[str], delay: float) -> typing.Tuple[typing.Dict[str, typing.Self], typing.Optional[typing.Tuple], typing.Dict[str, License]]:
        """
            Constructor for the Package that scrapes it from Hackage.

            This essentially makes the given package the root. Any dependencies are automagically found.

            # Arguments
            - `ident`: Some machine-friendly name of this package (e.g., `eflint`).
            - `url`: The URL to download from.
            - `download`: Whether to download the license files while at it.
            - `delay`: The delay (in seconds) between requests to avoid DoS'ing.
            - `last_request`: The second-based timestamp of the last request, if any.

            # Returns
            A tuple of all the found new Packages, plus a dependency tree in terms of identifiers.
        """

        last_request = None
        done = set()
        res = {}
        tree = (ident, [])
        licenses = {}

        i = 0
        todo = [(ident, url, tree[1])]
        while len(todo) > 0:
            ident, url, tree = todo.pop()
            i += 1
            print(f"Package {i}/{i + len(todo)}", end = "\r")
            sys.stdout.flush()

            # Check if we already did this one
            if ident in done:
                # Don't do anything, already in the parent set
                log(f"Not doing '{ident}', already done that")
                continue

            # Check if the download folder exists
            if download is not None:
                if os.path.exists(download):
                    log(f"License download folder '{download}' already exists")
                else:
                    log(f"License download folder '{download}' does not exist, creating...")
                    try:
                        os.makedirs(download)
                    except IOError as e:
                        error(f"Failed to create license download folder '{download}': {e}")
                        exit(e.code)

            # Wait if we already did a request
            now = time.time()
            if last_request is not None and now - last_request < delay:
                time.sleep(delay - (now - last_request))

            # Attempt to download the page
            log(f"Getting package page from '{url}'...")
            (html, last_request) = (requests.get(url, allow_redirects=True), time.time())
            if html.status_code != 200:
                warn(f"Failed to get package '{ident}' (skipping it)")
                log(f"Failed to get web page for package '{ident}' ({url})\n\nResponse:\n{'-' * 80}\n{html.text}\n{'-' * 80}\n")
                done.add(ident)
                continue

            # Parse the web page
            log(f"Parsing web page...")
            soup = bs4.BeautifulSoup(html.text, "html.parser")
            # Short title
            short = soup.find("div", id="content").h1.small.string
            log(f"  > short = '{short}'")
            # License (URL) / Deps
            license, license_url, deps = None, None, []
            for rule in soup.find("div", id="content").find("div", id="flex-container").find("div", id="properties").tbody.find_all("tr"):
                if rule.th.string == "License":
                    if rule.td.a is not None:
                        license = rule.td.a.string
                        license_url = "https://hackage.haskell.org{}".format(rule.td.a["href"])
                    else:
                        warn(f"Failed to get license body for package '{ident}' (no URL given)")
                        license = rule.td.string
                elif rule.th.string == "Dependencies":
                    deps = [(d.a.string, f"https://hackage.haskell.org{d.a['href']}") for d in rule.find_all("span") if "font-size: small" not in d["style"] ]
            log(f"  > license = '{license}'")
            log(f"  > license_url = '{license_url}'")
            log(f"  > deps = {deps}")

            # Download the license of this package
            license_body = None
            if license_url is not None:
                now = time.time()
                if now - last_request < delay:
                    time.sleep(delay - (now - last_request))
                log(f"Getting '{ident}' license from '{license_url}'...")
                (license_body, last_request) = (requests.get(license_url, allow_redirects=True), time.time())
                if html.status_code != 200:
                    warn(f"Failed to get license body for package '{ident}' (cannot verify license hash)")
                    log(f"Failed to get license for package '{ident}' ({license_url})\n\nResponse:\n{'-' * 80}\n{html.text}\n{'-' * 80}\n")

            # Write the body if requested
            license_hash = None
            if license_body is not None:
                # Hash it
                license_hash = hex(hash(license_body.text.strip()))[2:]
                log(f"  > license_hash = '{license_hash}'")
            else:
                license_hash = "<unhashed>"

            # Update our knowledge of unique licenses
            if license_hash not in licenses:
                # Create a unique license object name
                n_of_this_type = sum([1 if licenses[hash].type == license else 0 for hash in licenses])
                name = license if n_of_this_type == 0 else f"{license}({n_of_this_type})"

                # Generate a path if applicable
                path = None
                if download is not None:
                    # Ensure the parent directory exists
                    dir = os.path.join(download, license)
                    if not os.path.exists(dir):
                        try:
                            os.makedirs(dir)
                        except IOError as e:
                            error(f"Failed to create directory '{dir}': {e}")
                            exit(e.code)
                    path = os.path.join(dir, ident)

                # Build the object
                licenses[license_hash] = License(name, license, license_hash, path)

                # Write the body if told
                if license_body is not None and path is not None:
                    log(f"Writing license body to '{path}'...")
                    try:
                        with open(path, "w") as h:
                            h.write(license_body.text)
                    except IOError as e:
                        error(f"Failed to write '{ident}' license body to '{path}': {e}")
                        exit(e.code)

            # Add that this license refers to that license
            licenses[license_hash].packages.append(ident)

            # Alright build ourselves
            res[ident] = Package(ident, short, url, license, license_url, license_hash)
            done.add(ident)

            # Recursively add the dependencies to the todo
            for dident, durl in deps:
                ddeps = []
                tree.append((dident, ddeps))
                todo.append((dident, durl, ddeps))

        # Done
        return (res, tree, licenses)





##### ENTRYPOINT #####
def main(package: str, download: typing.Optional[str], output: str, delay: int, show_list: bool, trim: bool) -> int:
    log("Called with:")
    log("  - package  = '{}'".format(package))
    log("  - download = {}".format(f"'{download}'" if download is not None else "<not downloading>"))
    log("  - output   = {}".format(f"'{output}'" if output != "-" else "<stdout>"))
    log("  - list     = {}".format(show_list))
    log("  - trim     = {}".format(trim))

    # Get the URL out of the package
    url = hackagify(package)
    log(f"Resolved package '{package}' as '{url}'")

    # Obtain the dependencies
    (pkgs, deps, licenses) = Package.scrape(package, url, download, delay)

    # Decide on colours
    colors = output == "-" and supports_color()
    accent = "\033[92;1m" if colors else ""
    bold = "\033[1m" if colors else ""
    end = "\033[0m" if colors else ""

    # Prepare the handle
    out = sys.stdout
    if output != "-":
        try:
            out = open(output, "w")
        except IOError as e:
            error(f"Failed to open output file '{output}' for writing: {e}")
            return e.code

    # Write the unique licenses
    for type in set([licenses[hash].type for hash in licenses]):
        print(file=out)
        print(f"License {accent}{type}{end}", file=out)
        print("   Used by: ", file=out)
        for pkg in [ident for ident in pkgs if pkgs[ident].license == type]:
            print(f"   - {bold}{pkg}{end}", file=out)
        print(file=out)

    # Print some nice header
    return 0


# Actual entrypoint
if __name__ == "__main__":
    # Define arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("PACKAGE", type=str, help="Some package identifier to download the license + its dependency's licenses of.")
    parser.add_argument("-d", "--download", type=str, help="If given, downloads the licenses of all dependencies to the given folder.")
    parser.add_argument("-o", "--output", type=str, default="-", help="The output to write the list of dependencies and licenses to. Use '<stdout>' to write to stdout instead of a file.")
    parser.add_argument("-D", "--delay", type=float, default=0.5, help="The number of seconds to wait before sending requests to Hackage, to avoid DoS'ing them.")
    parser.add_argument("-l", "--list", action="store_true", help="If given, displays the packages as a linear list instead of as a tree.")
    parser.add_argument("-t", "--trim", action="store_true", help="If given, only shows the licenses used, not which package uses them.")
    parser.add_argument("--debug", action="store_true", help="If given, shows debug prints for the script.")

    # Parse the arguments
    args = parser.parse_args()
    DEBUG = args.debug

    # Run main
    exit(main(args.PACKAGE, args.download, args.output, args.delay, args.list, args.trim))
