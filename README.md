# hackage-license-scraper
Utility Python script that does what it says on the tin.


## Installation
Make sure you installed at least Python 3.9 or higher.

Also install the requirements in `requirements.txt` using pip, e.g.,
```bash
pip3 install -r requirements.txt
```


## Usage
Once you installed the dependencies, you can run the script by typing:
```bash
./get_licenses.py <package>
```
where `<package>` is some identifier used by Hackage to refer to the package. For example:
```bash
./get_licenses.py eflint
```
should get you the set of dependencies and licenses used for the `eflint` package.

### Output
You can optionally download all the license files by adding the `--download`-flag:
```bash
./get_licenses.py <package> --download <DIR_TO_DOWNLOAD_TO>
```

Similarly, you can also write the output to a file instead of stdout:
```bash
./get_licenses.py <package> --output <FILE_TO_WRITE_TO>
```

See `./get_licenses.py --help` for all options.

### Interpreting the output
TODO


## Contributing


## License
