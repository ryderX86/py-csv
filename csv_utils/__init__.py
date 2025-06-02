from typing import Any, Literal
from enum import Enum
from inspect import currentframe
import json
import re

CSV_REGEX = r"(?:(?P<cell>(\".+\")|(?:[^,\"\n]*)))(?P<term>[,\n]|$)"
CELL_ENCLOSED_REGEX = r"\"[\",\n]*"
CSV_REGEX_CELL_ESCAPED = r"\"[\",\n]\""
CELL_TO_STR_RE = r"[\",\n]"

_csv_is_compiled = False

strict_tables = False

def _strict_tables():
    if type(strict_tables) is not bool:
        raise TypeError("strict_tables must be 'bool', not '%s'"
                        % type(strict_tables).__name__)
    return strict_tables

def compile_regex():
    global csv_regex_compiled
    global csv_regex_cell_escaped_compiled
    global cell_enclosed_regex_compiled
    global cell_to_str_re_compiled
    global _csv_is_compiled
    csv_regex_compiled = re.compile(CSV_REGEX)
    cell_enclosed_regex_compiled = re.compile(CELL_ENCLOSED_REGEX)
    csv_regex_cell_escaped_compiled = re.compile(CSV_REGEX_CELL_ESCAPED)
    cell_to_str_re_compiled = re.compile(CELL_TO_STR_RE)
    _csv_is_compiled = True

def _cell_enclosed_finditer(string:str) -> list[re.Match]:
    if _csv_is_compiled:
        return [*cell_enclosed_regex_compiled.finditer(string)]
    else:
        return [*re.finditer(CELL_ENCLOSED_REGEX, string)]
    
def _cell_escaped_finditer(string:str) -> list[re.Match]:
    if _csv_is_compiled:
        return [*csv_regex_cell_escaped_compiled.finditer(string)]
    else:
        return [*re.finditer(CSV_REGEX_CELL_ESCAPED, string)]

def _csv_from_str_regex(string:str) -> list[re.Match]:
    if _csv_is_compiled:
        return [*csv_regex_compiled.finditer(string)]
    else:
        return [*re.finditer(CSV_REGEX, string)]

class CSV:
    allowed_converstion_types = (int, float, Literal)
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
        self.uses_custom_regex:bool = False
        self._csv_regex:None|re.Pattern = None
        self._cell_enclosed_regex:None|re.Pattern = None
        self._cell_escaped_regex:None|re.Pattern = None
        self._cell_to_str_re:None|re.Pattern = None

    def __repr__(self):
        return "CSV(rows=%s, cellend=%s, rowend=%s, escape=%s)" % (
            repr(self._rows),
            repr(self._cellend),
            repr(self._rowend),
            repr(self._escape)
        )
    
    def __getitem__(self, key:int|tuple) -> list[Any]:
        if type(key) is int:
            if key > (len(self._rows) - 1):
                if _strict_tables():
                    raise IndexError("row index out of range")
                return self._get_blank_row()
            return self._rows[key]
        elif type(key) is tuple:
            if len(key) > 2:
                raise SyntaxError("CSV[]: expected 2 indexes, got %s"
                                  % len(key))
            elif type(key[0]) is not int or type(key[1]) is not int:
                raise TypeError("CSV[]: indexes must be type 'int'")
            if key[0] > (len(self._rows) - 1):
                if _strict_tables():
                    raise IndexError("row index out of range")
                return None
            elif key[1] > (len(self._rows[key[0]]) - 1):
                if _strict_tables():
                    raise IndexError("column index out of range")
                return None
            return self._rows[key[0]][key[1]]
        else:
            raise TypeError("CSV[]: expected 'int' or 'tuple[int]', got '%s'"
                            % type(key).__name__)
        
    
    def __setitem__(self, key:int|tuple, value:list[Any]|Any):
        if type(key) is int and type(value) is list:
            if key > (len(self._rows) - 1):
                if _strict_tables():
                    raise IndexError("row index out of range")
                for rowi in range(len(self._rows) + 1, key):
                    self._rows.append(self._get_blank_row())
            if len(value) > (len(self._rows[0]) - 1):
                if _strict_tables():
                    raise IndexError("row has too many values "
                                     "(try setting this module's variable strict_tables=False)")
                for rowi in range(len(self._rows)):
                    for col in range(len(self._rows[rowi]) - 1, len(list)):
                        self._rows[rowi].append(None)
            self._rows[key] = value
        elif type(key) is tuple:
            row = key[0]
            col = key[1]
            if row > (len(self._rows) - 1):
                if _strict_tables():
                    raise IndexError("row index out of range")
                for rowi in range(len(self._rows) - 1, row):
                    self._rows.append(self._get_blank_row())
            if col > (len(self._rows[0]) - 1):
                if _strict_tables():
                    raise IndexError("column index out of range")
                for rowi in range(len(self._rows)):
                    for coli in range(len(self._rows[rowi]) - 1, col):
                        self._rows[rowi].append(None)
            self._rows[row][col] = value
        else:
            raise TypeError("CSV[]: expected 'int' or 'tuple[int]', got '%s'"
                            % type(key).__name__)

    def _get_blank_row(self):
        if len(self._rows) > 0:
            return [None for _ in self._rows[0]]
        else:
            return [None]

    @classmethod
    def _raise_for_enum(cls, origin:str, value:Enum):
        raise SyntaxError(f"CSV.{origin}: value was of type 'enum.Enum', but was not an allowed value {str(cls.allowed_converstion_types)}, instead was {type(value).__name__}")

    @classmethod
    def _check_enum(cls, value:Enum) -> bool:
        if value in cls.allowed_converstion_types:
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
        def _repl_csv_from_str_regex(data) -> list[str]:
            return [*re.finditer(_csv_regex, data)]
        def _repl_cell_enclosed_regex(data) -> list[str]:
            return [*re.finditer(_cell_enclosed_regex, data)]
        def _repl_cell_escaped_regex(data) -> list[str]:
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

        _class_out = cls(rows=rows_in, cellend=cellend, rowend=rowend, escape=escape)
        if _uses_custom_regex:
            _class_out.uses_custom_regex = True
            _class_out._csv_regex = _csv_regex
            _class_out._cell_enclosed_regex = _cell_enclosed_regex
            _class_out._cell_escaped_regex = _cell_escaped_regex
            _class_out._cell_to_str_re = _cell_to_str_re
        return _class_out

    
    def to_str(self, *, blank:str=""):
        if type(blank) is not str:
            raise TypeError("CSV.to_str: arg 'blank' must be type 'str', not '%s'"
                            % type(blank).__name__)
        cells_out = [["" for _ in row] for row in self._rows]
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
        cells_out = self._rowend.join(cells_out)
        return cells_out
    
    def to_list(self, *, headers:list[str]|tuple[str]|None=None) -> dict:
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
                pass # It's already in the format we need :)
            case tuple():
                headers = list(**headers) # Slight change
            case _:
                raise TypeError("CSV.to_dict: 'headers' must be type 'list', 'tuple' or 'NoneType', not %s" % type(headers).__name__)
        
        if check_headers is True:
            # Match all the headers and make sure they're all str, if not,
            # if they're compatible with str, go for it, otherwise, raise
            # an error.
            for index in range(len(headers)):
                match headers[index]:
                    case str():
                        pass
                    case self.allowed_conversion_types:
                        headers[index] = str(headers[index])
                    case Enum():
                        if self._check_enum(headers[index]):
                            headers[index] = str(headers[index])
                        else:
                            self._raise_for_enum('to_dict', headers[index])
                    case _:
                        raise TypeError("CSV.to_dict: header at position %s was type %s (expected one of the following: %s)" % (index, type(headers[index]).__name__, self.allowed_converstion_types))
        
        list_out = [None for x in range(rows)]
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

        This is a very simple function, as it basically wraps self.to_list()
        in json.dumps()
        """
        if root_name is None:
            return json.dumps(self.to_list)
        else:
            return json.dumps({root_name: self.to_list})
        

def str_from_cell(cell:str, parent:CSV) -> str:
    matches: list[re.Match]
    if _csv_is_compiled:
        matches = [*cell_to_str_re_compiled.finditer(cell)]
    elif parent.uses_custom_regex:
        matches = [*re.finditer(parent._cell_to_str_re, cell)]
    else:
        matches = [*re.finditer(CELL_TO_STR_RE, cell)]
    cell_out = cell
    if len(matches) > 0:
        cell_out = parent._escape + cell_out + parent._escape
        for match in matches:
            matched_str = match.string[match.start():match.end()]
            cell_out.replace(matched_str, f'{parent._escape}{matched_str}')
    del matches
    return cell_out