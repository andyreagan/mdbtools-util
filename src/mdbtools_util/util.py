import logging
import re
from subprocess import PIPE, Popen, run

log_fmt = "[%(asctime)s - %(levelname)s] - %(name)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_fmt)
logger = logging.getLogger(__file__)


def fix_column_name(x: str) -> str:
    if re.search("[^a-zA-Z0-9_]", x):
        x = re.sub("[^a-zA-Z0-9_]", "_", x).replace("___", "_").replace("__", "_")
    if x[0].isdigit():
        x = "_" + x
    return x


def extract_mdb_table(
    filename: str,
    input_table: str,
    output_table: str,
    delimiter: str,
    escape: str = "@",
    date_format: str = "%F",
    time_format: str = "%F %T",
    row_delimiter: str = "\\n",
    quote_char: str = '"',
    skip_header: bool = True,
    escape_invisible: bool = True,
    no_quote: bool = False,
) -> str:
    """
    Extract the table as csv from the .mdb database using command line tool mdb-export.
    """
    command = ["mdb-export"]
    options = ["-X", escape, "-d", delimiter, "-D", date_format, "-T", time_format, "-R", row_delimiter, "-q", quote_char]
    args = [filename, input_table]

    bool_options = []
    if skip_header:
        bool_options.append("-H")
    if escape_invisible:
        # note, `-e` is only available with v0.9.1
        # see https://github.com/mdbtools/mdbtools/pull/222
        bool_options.append("-e")
    if no_quote:
        bool_options.append("-Q")

    with open(output_table, 'w') as sink:
        run(command + bool_options + options + args, stdout=sink)

    logger.info(
        "successfully ran extract of {input_table} from {filename} to {output_table}".format(
            input_table=input_table, filename=filename, output_table=output_table
        )
    )
    return output_table

    # # return a stream instead
    # proc = Popen(mdb_export_cmd,
    #              shell=True,
    #              stdout=PIPE)
    # with proc.stdout as stream:
    #     return stream


def fix_mdb_column_definition(column_definition: str, old_table_name: str, new_table_name: str) -> str:
    fixed_column_definition = []
    for line in column_definition.split("\n"):
        for idx, match in enumerate(re.findall(r"\"(.+?)\"", line)):
            # v1.0.0 of mdbtools lowercases table names
            # see: https://github.com/mdbtools/mdbtools/pull/322
            if match == old_table_name or match == old_table_name.lower():
                if (idx == 0) and (
                    re.search('ALTER TABLE "{}"'.format(match), line)  # noqa: W503
                    or re.search('CREATE TABLE "{}"'.format(match), line)  # noqa: W503
                    # v1.0.0 uses the IF NOT EXISTS on the create statement
                    # see: https://github.com/mdbtools/mdbtools/pull/321
                    or re.search('CREATE TABLE IF NOT EXISTS "{}"'.format(match), line)  # noqa: W503
                    or re.search('DROP TABLE IF EXISTS "{}"'.format(match), line)
                ):  # noqa: W503
                    line = re.sub(match, new_table_name, line, count=1)
                else:
                    line = re.sub(match, fix_column_name(match), line)
            else:
                line = re.sub(match, fix_column_name(match), line)
        line = re.sub("SERIAL,", "INTEGER,", line)
        line = re.sub("SERIAL$", "INTEGER", line)
        line = re.sub("TEXT,", "LONG VARCHAR,", line)
        line = re.sub("TEXT$", "LONG VARCHAR", line)
        fixed_column_definition.append(line)
    fixed_column_definition_str = "\n".join(fixed_column_definition)
    fixed_column_definition_str = (
        fixed_column_definition_str.replace('"', "")
        .replace("SET client_encoding = 'UTF-8';", "")
        .replace("CREATE UNIQUE INDEX", "-- CREATE UNIQUE INDEX")
        .replace("CREATE INDEX", "-- CREATE INDEX")
        .replace("COMMENT ON COLUMN", "-- COMMENT ON COLUMN")
        .replace("COMMENT ON TABLE", "-- COMMENT ON TABLE")
        .replace("\tDesc\t", "\tDescription\t")
        .replace("\tNew\t", "\tNewly\t")
    )
    # fixed_column_definition_str = fixed_column_definition_str.replace("ALTER TABLE", "-- ALTER TABLE")
    return fixed_column_definition_str


def get_mdb_column_definition(mdb_path: str, mdb_table_name: str, pg_table_name: str) -> str:
    print(mdb_path + ": " + mdb_table_name + " -> " + pg_table_name)
    mdb_tables = (
        Popen(
            ["mdb-tables", "-1", mdb_path], stdout=PIPE
        )
        .communicate()[0]
        .decode("utf-8")
        .split("\n")
    )
    if mdb_table_name not in mdb_tables:
        raise Exception("table not found: options are" + str(mdb_tables))
    else:
        column_definition = (
            Popen(
                [
                    "mdb-schema",
                    "--table",
                    mdb_table_name,
                    "--drop-table",
                    "--relations",
                    "--indexes",
                    "--default-values",
                    "--not-null",
                    mdb_path,
                    "postgres"
                ],
                stdout=PIPE,
            )
            .communicate()[0]
            .decode("utf-8")
        )
    return fix_mdb_column_definition(column_definition, mdb_table_name, pg_table_name)
