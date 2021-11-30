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
) -> str:
    """Extract the table as csv from the .mdb database using command line tool mdb-export.

    Reference for mdb-export: https://linux.die.net/man/1/mdb-export
    -H, --no-header                   Suppress header row.
    -d, --delimiter=char              Specify an alternative column delimiter. Default is comma.
    -R, --row-delimiter=char          Specify a row delimiter
    -Q, --no-quote                    Don't wrap text-like fields in quotes.
    -q, --quote=char                  Use <char> to wrap text-like fields. Default is double quote.
    -X, --escape=format               Use <char> to escape quoted characters within a field. Default is doubling.
    -e, --escape-invisible            Use C-style escaping for return (\r), tab (\t), line-feed (\n), and back-slash (\\) characters.
    -D: Set the date format (see strftime(3) for details) (https://linux.die.net/man/3/strftime)
    """
    with open(output_table, 'w') as sink:
        run(["mdb-export", "-X", escape, "-H", "-d", delimiter, "-D", "%F %T", "-R", "\\n", "-q", '"', "-e", filename, input_table], stdout=sink)
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
            if match == old_table_name:
                if (idx == 0) and (
                    re.search('ALTER TABLE "{}"'.format(match), line)  # noqa: W503
                    or re.search('CREATE TABLE "{}"'.format(match), line)  # noqa: W503
                    or re.search('DROP TABLE IF EXISTS "{}"'.format(match), line)
                ):  # noqa: W503
                    line = re.sub(match, new_table_name, line, count=1)
                else:
                    line = re.sub(match, fix_column_name(match), line)
            else:
                line = re.sub(match, fix_column_name(match), line)
        line = re.sub("SERIAL,", "INTEGER,", line)
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
    # from https://github.com/massmutual/experience-study/blob/master/study/migrate.py#L136
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
