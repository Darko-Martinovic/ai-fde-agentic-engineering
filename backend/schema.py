"""What every table of UnderCover's schema is made with: the one `MetaData` the
tables are part of, and the kinds of column they share."""

from sqlalchemy import Column, Integer, MetaData, Text

metadata = MetaData()


def text_column(
    name: str, *, nullable: bool = False, primary_key: bool = False
) -> Column:
    """A column of text, required unless it's nullable."""
    return Column(name, Text, nullable=nullable, primary_key=primary_key)


def counter(name: str) -> Column:
    """A key that counts up, as each row is added."""
    return Column(name, Integer, primary_key=True, autoincrement=True)
