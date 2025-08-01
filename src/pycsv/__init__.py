from typing import Any, Literal
from enum import Enum
import json
import re

CSV_REGEX = r"(?:(?P<cell>(\".+\")|(?:[^,\"\n]*)))(?P<term>[,\n]|$)"
QUOTED_CELL_RE = r"\"[\",\n]*"
ESCAPED_CELL_RE = r"\"[\",\n]\""
ESCAPE_CHARS_RE = r"[\",\n]"

_regexp_is_compiled = False

strict_tables:bool = False
"""
Module wide variable to determine how
lookups & setters will be treated.

`True`: Lookups to and setting values
outside of what's already been added will
result in a `IndexError`.

`False`: Lookups to and setting values
outside of what's already been added
will NOT result in a `IndexError`.

Examples:

`True`
```
from pycsv import CSV

csv = CSV([["col0row0", "col1row0"], ["col0row1", "col1row1"]])

print(csv[2,0]) # Will raise an IndexError
csv[2,0] = True # Will also raise an IndexError
```

`False`
```
from pycsv import CSV
import pycsv
pycsv.strict_tables = False

csv = CSV([["col0row0", "col1row0"], ["col0row1", "col1row1"]])

print(csv[2,0]) # Will print None

# Will add a third column and set
# the contents of row 0 of column 3 to True
csv[2,0] = True
```
"""

def _tables_are_strict():
    if type(strict_tables) is not bool:
        raise TypeError("strict_tables must be 'bool', not '%s'"
                        % type(strict_tables).__name__)
    return strict_tables

def compile_regex():
    global _csv_regex_compiled
    global _csv_regex_cell_escaped_compiled
    global _quoted_cell_re_compiled
    global _escape_chars_re_compiled
    global _regexp_is_compiled
    _csv_regex_compiled = re.compile(CSV_REGEX)
    _quoted_cell_re_compiled = re.compile(QUOTED_CELL_RE)
    _csv_regex_cell_escaped_compiled = re.compile(ESCAPED_CELL_RE)
    _escape_chars_re_compiled = re.compile(ESCAPE_CHARS_RE)
    _regexp_is_compiled = True

def _cell_enclosed_finditer(string:str) -> list[re.Match]:
    if _regexp_is_compiled:
        return [*_quoted_cell_re_compiled.finditer(string)]
    else:
        return [*re.finditer(QUOTED_CELL_RE, string)]
    
def _cell_escaped_finditer(string:str) -> list[re.Match]:
    if _regexp_is_compiled:
        return [*_csv_regex_cell_escaped_compiled.finditer(string)]
    else:
        return [*re.finditer(ESCAPED_CELL_RE, string)]

def _csv_from_str_regex(string:str) -> list[re.Match]:
    if _regexp_is_compiled:
        return [*_csv_regex_compiled.finditer(string)]
    else:
        return [*re.finditer(CSV_REGEX, string)]

class CSV:
    allowed_converstion_types = (int, float, Literal, complex, bool)
    def __init__(self, rows:list[list[Any]]|None=None, *, cellend:str=',', rowend:str='\n', escape:str='"'):
        match rows:
            case None:
                rows = [[None]]
            case list():
                pass
            case _:
                raise SyntaxError("'rows' must be type 'list', not %s" % type(rows).__name__)
        match cellend:
            case str():
                pass
            case _:
                raise SyntaxError("'cell_seperator' must be type 'str', not %s" % type(cellend.__name__))
        match rowend:
            case str():
                pass
            case _:
                raise SyntaxError("'row_seperator' must be type 'str', not %s" % type(rowend).__name__)
        match escape:
            case str():
                pass
            case _:
                raise SyntaxError("'escape' must be type 'str', not %s" % type(escape).__name__)
        for row in rows:
            match row:
                case list():
                    pass
                case _:
                    raise SyntaxError("CSV.__init__: row %s is not type 'list'" % rows.index(row))

        self._rows = rows
        self._cellend = cellend
        self._rowend = rowend
        self._escape = escape
        self._csv_regex:None|re.Pattern = None
        self._cell_enclosed_regex:None|re.Pattern = None
        self._cell_escaped_regex:None|re.Pattern = None
        self._cell_to_str_re:None|re.Pattern = None

        # make sure all the rows & columns are the same length
        max_row_size = len(max(self._rows))
        min_row_size = len(min(self._rows))
        if min_row_size < max_row_size:
            for i in range(len(self._rows)):
                row = self._rows[i]
                if len(row) == max_row_size:
                    continue
                else:
                    self._rows[i].extend([None for _ in range(max_row_size - min_row_size)])

        col_lengths = [len(i) for i in self._rows]
        max_col_size = max(col_lengths)
        min_col_size = min(col_lengths)
        if max_col_size > min_col_size:
            for i in range(self.col_count):
                column = self.get_col(i)
                if len(column) < max_col_size:
                    column_discrepency = max_col_size - len(column)
                    range_start = len(column)
                    for x in range(range_start, column_discrepency):
                        self[i,x] = None # i THINK this works, TODO: come back to it

    def __repr__(self):
        return "CSV(rows=%s, cellend=%s, rowend=%s, escape=%s)" % (
            repr(self._rows),
            repr(self._cellend),
            repr(self._rowend),
            repr(self._escape)
        )
    
    def __str__(self, *, blank:str=""):
        return self.to_str()
    
    def get_col(self, col_index):
        return [self[i,col_index] for i in range(len(self._rows))]
    
    @property
    def regexp(self):
        return self._csv_regex
    
    @regexp.setter
    def regexp(self, value:str|re.Pattern):
        if type(value) == re.Pattern:
            self._csv_regex = value
        elif type(value) == str:
            value = re.compile(value)
            self._csv_regex = value
        else:
            raise TypeError("expected str or re.Pattern, not %s" % repr(type(value).__name__))
        
    @property
    def enclosed_cell_regexp(self):
        return self._cell_enclosed_regex
    
    @enclosed_cell_regexp.setter
    def enclosed_cell_regexp(self, value):
        if type(value) == re.Pattern:
            self._cell_enclosed_regex = value
        elif type(value) == str:
            value = re.compile(value)
            self._cell_enclosed_regex = value
        else:
            raise TypeError("expected str or re.Pattern, not %s" % repr(type(value).__name__))
        
    @property
    def escaped_cell_regexp(self):
        return self._cell_escaped_regex
    
    @escaped_cell_regexp.setter
    def escaped_cell_regexp(self, value):
        if type(value) == re.Pattern:
            self._cell_escaped_regex = value
        elif type(value) == str:
            value = re.compile(value)
            self._cell_escaped_regex = value
        else:
            raise TypeError("expected str or re.Pattern, not %s" % repr(type(value).__name__))
        
    @property
    def cell_str_conversion_regexp(self):
        if self.uses_custom_regex:
            return self._cell_to_str_re
    
    @cell_str_conversion_regexp.setter
    def cell_str_conversion_regexp(self, value):
        if type(value) == re.Pattern:
            self._cell_to_str_re = value
        elif type(value) == str:
            value = re.compile(value)
            self._cell_to_str_re = value
        else:
            raise TypeError("expected str or re.Pattern, not %s" % repr(type(value).__name__))
        
    @property
    def uses_custom_regex(self):
        if any([self._cell_enclosed_regex,
                self._cell_escaped_regex,
                self._csv_regex,
                self._cell_to_str_re]):
            return True
        else:
            return False
    
    @uses_custom_regex.setter
    def uses_custom_regex(self, val:bool):
        raise NotImplementedError("This value does not need to be set, as it is set automatically when using the setter functions.")
    
    def __getitem__(self, key:int|tuple) -> list[Any]|None: 
        if type(key) is int:
            if key > (len(self._rows) - 1):
                if _tables_are_strict():
                    raise IndexError("row index out of range")
                return self._get_blank_row()
            return self._rows[key]
        elif type(key) is tuple:
            if len(key) > 2 or len(key) < 2:
                raise SyntaxError("CSV[]: expected 2 indexes, got %s"
                                  % len(key))
            elif type(key[0]) is not int or type(key[1]) is not int:
                raise TypeError("CSV[]: indexes must be type 'int'")
            if key[0] > (len(self._rows) - 1):
                if _tables_are_strict():
                    raise IndexError("row index out of range")
                return None
            elif key[1] > (len(self._rows[key[0]]) - 1):
                if _tables_are_strict():
                    raise IndexError("column index out of range")
                return None
            return self._rows[key[0]][key[1]]
        else:
            raise TypeError("CSV[]: expected 'int' or 'tuple[int]', got '%s'"
                            % type(key).__name__)
        
    def append_row(self, row:list[Any]):
        """
        Add an entire row to the table.

        This must be a list of objects.

        Within the list, if the columns aren't all filled,
        they will be set to None then appended to the row.
        """
        if type(row) is not list:
            raise TypeError("expected 'list', not '%s'"
                            % type(row).__name__)
        if len(row) < len(self._rows[0]):
            for _ in range(len(row), len(self._rows[0])):
                row.append(None)
        self._rows.append(row)

    def append_col(self, column:list[Any]):
        """
        Add an entire column to the table.

        The column will be added after the
        last column (index -1).
        
        This should be a list of objects,
        same as append_row(). They will be
        inserted from 0:(-1) in the list to
        rows 0:(-1).

        Within the list, if all cells aren't
        filled, they will be set to None then
        appended to the remaining cells in the
        columns/rows.
        """
        if type(column) is not list:
            raise TypeError("expected 'list', not '%s'"
                            % type(column).__name__)
        if len(column) < len(self._rows):
            self._set_column_count(len(column))

        for rowi in range(len(column)):
            self._rows[rowi].append(column[rowi])
    
    def __setitem__(self, key:int|tuple, value:list[Any]|Any): # TODO: add support for key ranges
        """
        Setter for CSV[i,i] or CSV[i] (row)

        If calling this as CSV[i] (setting a row),
        the input MUST be a list.

        If calling as CSV[i,i], (setting a single cell)
        the input can be any value.
        """
        if type(key) is int and type(value) is list:
            if len(value) > (len(self._rows[0]) - 1):
                if _tables_are_strict():
                    raise IndexError("row has too many values "
                                     "(try setting this module's variable strict_tables=False)")
                self._set_column_count(key)
            if key > (len(self._rows) - 1):
                if _tables_are_strict():
                    raise IndexError("row index out of range")
                self._set_row_count(key)
            self._rows[key] = value
        elif type(key) is tuple:
            row = key[0]
            col = key[1]
            if row > (len(self._rows) - 1):
                if _tables_are_strict():
                    raise IndexError("row index out of range")
                self._set_row_count(row)
            if col > (len(self._rows[0]) - 1):
                if _tables_are_strict():
                    raise IndexError("column index out of range")
                self._set_column_count(col)
            self._rows[row][col] = value
        else:
            raise TypeError("CSV[]: expected 'int' or 'tuple[int]', got '%s'"
                            % type(key).__name__)

    def _get_blank_row(self):
        """
        Constructor for a blank row
        """
        if len(self._rows) > 0:
            return [None for _ in self._rows[0]]
        else:
            return [None]
        
    def _set_column_count(self, col_count:int):
        """
        Function to make sure all the
        rows have the same amount of columns.
        """
        # TODO: find a better optimized way of finding the largest index
        largest_row:int = 0
        for row in self._rows:
            _row_len = len(row)
            if _row_len > largest_row:
                largest_row = _row_len
        if largest_row > col_count:
            col_count = largest_row

        for index in range(len(self._rows)):
            _row_len = len(self._rows[index])
            if _row_len < col_count:
                for _ in range(_row_len, col_count):
                    self._rows[index].append(None)

    def _set_row_count(self, row_count:int):
        """
        Function to add blank rows.
        """
        current_row_count = len(self._rows)

        if row_count > current_row_count:
            for _ in range(current_row_count, row_count):
                self._rows.append(self._get_blank_row())

    @classmethod
    def _raise_for_enum(cls, origin:str, value:Enum):
        raise SyntaxError(f"CSV.{origin}: value was of type 'enum.Enum', but was not an allowed value {str(cls.allowed_converstion_types)}, instead was {type(value).__name__}")

    @classmethod
    def is_allowed_type(cls, value) -> bool:
        """
        Checks if a given value is allowed in conversion.
        """
        if type(value) in cls.allowed_converstion_types:
            return True
        else:
            return False

    @classmethod
    def from_str(cls, data:str, *, cellend:str=',', rowend:str='\n', escape:str='"'):
        """
        Generate (and return) an instance of this class from a string (i.e. read directly from a CSV file)

        arg data: Contents of the CSV table
        arg cell_seperator: The character that seperates cells (in 99% of cases
        this will be a comma ',')
        arg row_seperator: The character that seperates rows of cells (in 99%
        of cases this will be a newline '\n')
        arg escape_char: The character that escapes other characters. This is
        mostly a double quote '"', but in some cases can be a backslash '\\'
        """
        # If regex needs to be replaced:
        _csv_regex = r"(?:(?P<cell>({e}.+{e})|(?:[^{c}{e}{r}]*)))(?P<term>[{c}{r}]|$)".replace(r'{e}', escape).replace(r'{r}', rowend).replace('{c}', cellend)
        _cell_enclosed_regex = r"{e}[{e}{c}{r}]*".replace(r'{e}', escape).replace(r'{r}', rowend).replace('{c}', cellend)
        _cell_escaped_regex = r"{e}[{e}{c}{r}]{e}".replace(r'{e}', escape).replace(r'{r}', rowend).replace('{c}', cellend)
        _cell_to_str_re = r"[{e}{c}{r}]".replace(r'{e}', escape).replace(r'{r}', rowend).replace('{c}', cellend)
        _uses_custom_regex = False
        def _repl_csv_from_str_regex(data) -> list[re.Match]:
            return [*re.finditer(_csv_regex, data)]
        def _repl_cell_enclosed_regex(data) -> list[re.Match]:
            return [*re.finditer(_cell_enclosed_regex, data)]
        def _repl_cell_escaped_regex(data) -> list[re.Match]:
            return [*re.finditer(_cell_escaped_regex, data)]
        if cellend != ',' or rowend != '\n' or escape != '"':
            __csv_from_str_regex = _repl_csv_from_str_regex
            __cell_enclosed_regex = _repl_cell_enclosed_regex
            __cell_escaped_regex = _repl_cell_escaped_regex
            _uses_custom_regex = True
        else:
            __csv_from_str_regex = _csv_from_str_regex
            __cell_enclosed_regex = _cell_enclosed_finditer
            __cell_escaped_regex = _cell_escaped_finditer
        regex_data = __csv_from_str_regex(data)
        rows_in = []
        current_row = []
        for m in regex_data:
            matched_str = m.group('cell')
            cell_terminator = m.group('term')
            if m.groupdict()['cell'] == matched_str:
                if cell_terminator == cellend:
                    current_row.append(matched_str)
                elif cell_terminator == rowend:
                    current_row.append(matched_str)
                    rows_in.append(current_row)
                    current_row = []
                else:
                    # data is finished
                    current_row.append(matched_str)
                    rows_in.append(current_row)
                    del current_row
                    break # keeps going on for some reason...
            else:
                raise Exception("CSV.from_str: re returned a match of unknown type: '%s' "
                                "(expected 'cell')" % str(matched_str))
        
        for i in range(len(rows_in)):  # for row in rows_in
            row = rows_in[i]
            for x in range(len(row)): # for cell in row
                cell = row[x]
                
                if len(cell) < 1:
                    pass
                elif cell[0] == escape and cell[-1] == escape:
                    # The entire cell is escaped
                    cell = cell[1:-1]
                    ma = __cell_enclosed_regex(cell)
                    for match in ma:
                        matched_str = match.string[match.start():match.end()]
                        cell.replace(matched_str, matched_str[1])
                elif __cell_escaped_regex(cell):
                    ma = __cell_escaped_regex(cell)
                    for match in ma:
                        matched_str = match.string[match.start():match.end()]
                        cell.replace(matched_str, matched_str[1])
                rows_in[i][x] = cell # rows_in.index(row).index(cell) = cell_

        _instance_out = cls(rows=rows_in, cellend=cellend, rowend=rowend, escape=escape)
        if _uses_custom_regex:
            _instance_out.regexp = _csv_regex
            _instance_out.enclosed_cell_regexp = _cell_enclosed_regex
            _instance_out.escaped_cell_regexp = _cell_escaped_regex
            _instance_out.cell_str_conversion_regexp = _cell_to_str_re
        return _instance_out

    
    def to_str(self, *, blank:str=""):
        if type(blank) is not str:
            raise TypeError("CSV.to_str: arg 'blank' must be type 'str', not '%s'"
                            % type(blank).__name__)
        # beautiful type declaration
        cells_out: (list[list | str] | str) = [["" for _ in row] for row in self._rows]
        for row_index in range(len(self._rows)): # for row in rows
            row = self._rows[row_index] 
            row_out = row
            for cell_index in range(len(row)): # for cell in row
                if type(row[cell_index]) is not str:
                    if row[cell_index] is None:
                        row[cell_index] = blank
                    else:
                        row[cell_index] = str(row[cell_index])
                row_out[cell_index] = str_from_cell(row[cell_index], self)
            cells_out[row_index] = self._cellend.join(row_out)
        cells_out = self._rowend.join(cells_out) # type: ignore
        return cells_out
    
    def to_list(self, *, headers:list[str]|tuple[str]|None=None) -> list:
        """
        Generate a JSON-compatible list based on the contents of this instance.

        If headers are specified, the top row will be treated as values; otherwise,
        the top row will be treated as the keys.
        """
        check_headers:bool = True

        rows = self._rows

        match headers:
            case None:
                headers = self._rows[0]
                # Since we're using the first row as the headers...
                del rows[0]
                # we don't need these anymore.
                check_headers = False
            case list():
                pass # It's already in the format we need
            case tuple():
                headers = list(*headers) # Slight change
            case _:
                raise TypeError("CSV.to_dict: 'headers' must be type 'list', 'tuple' or 'NoneType', not %s" % type(headers).__name__)
        
        if check_headers is True:
            # Check all the headers and make sure they're all str, if not,
            # if they're compatible with str, go for it, otherwise, raise
            # an error.
            for index in range(len(headers)):
                if type(headers[index]) is str:
                    pass
                elif type(headers[index]) in self.allowed_converstion_types:
                    headers[index] = str(headers[index])
                # I have literally zero clue what this was
                # doing in the first place.
                # elif isinstance(headers[index], Enum):
                #     if not self.is_allowed_type(headers[index]):
                #         self._raise_for_enum('to_list', headers[index])
                #     headers[index] = str(headers[index])
                else:
                    raise TypeError("CSV.to_list: header at position %s was type %s (expected one of the following: %s)" % (index, type(headers[index]).__name__, self.allowed_converstion_types))
        
        list_out:list[Any] = [None for x in range(len(rows))]
        for row in rows:
            row_out = {}
            for index in range(len(row)):
                cell = row[index]
                row_out[headers[index]] = cell
            list_out[rows.index(row)] = row_out
        
        return list_out
    
    def to_json(self, *, headers:list[str]|tuple[str]|None=None, root_name:str|None=None) -> str:
        """
        Generate a JSON string based on the contents of this instance.

        Wrapper for json.dumps(self.to_list())
        """
        if root_name is None:
            return json.dumps(self.to_list())
        else:
            return json.dumps({root_name: self.to_list()})
    
    @property
    def row_count(self):
        return len(self._rows)
    
    @property
    def col_count(self):
        return len(max(self._rows))
    
    @property
    def cell_count(self):
        return self.row_count * self.col_count
    
    @property
    def populated_cell_count(self):
        populated_cells = 0
        for row in self._rows:
            for cell in row:
                if cell != None:
                    populated_cells += 1
        return populated_cells
        

def str_from_cell(cell:str, parent:CSV) -> str:
    if cell is None:
        return ""
    
    matches: list[re.Match]
    if _regexp_is_compiled:
        matches = [*_escape_chars_re_compiled.finditer(cell)]
    elif parent.uses_custom_regex:
        matches = [*parent.cell_str_conversion_regexp.finditer(cell)] # type: ignore
    else:
        matches = [*re.finditer(ESCAPE_CHARS_RE, cell)]
    cell_out = cell
    if len(matches) > 0:
        cell_out = parent._escape + cell_out + parent._escape
        for match in matches:
            matched_str = match.string[match.start():match.end()]
            cell_out.replace(matched_str, f'{parent._escape}{matched_str}')
    del matches
    return cell_out