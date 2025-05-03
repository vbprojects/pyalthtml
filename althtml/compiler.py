import re
from typing import List, Dict, Tuple, Optional, Any

class AlthtmlCompiler:
    """
    Althtml Compiler
    Compiles althtml source code to HTML based on the defined specification.

    Features:
    - Indentation-based hierarchy
    - Global variables (set keyword, string substitution)
    - Simple and Argument Macros (@ invocation, ! calls)
    - ID shortcut (#)
    - Literal text (|), implicit text (whitespace collapsed), quoted implicit text
    - Self-closing tags (tag>)
    - Raw blocks for variables
    - Raw directive handling (outputs block content literally)
    - Raw line handling (outputs line content literally after 'raw ')
    - Raw@ directive handling (outputs block/line content literally WITH variable substitution)
    - No automatic HTML escaping
    - Minimal fatal error handling (Indentation, Syntax, Undefined)
    """

    def __init__(self):
        """Initializes the compiler state."""
        self.variables: Dict[str, str] = {}  # Global store for variables
        self.macros: Dict[str, Dict[str, Any]] = {} # Global store for macros { name: { definition_lines: [], is_arg_macro: bool, arg_count: int } }
        self.html_output: str = ''
        self.tag_stack: List[Dict[str, Any]] = [] # { tag_name: str, indent_level: int, self_closing: bool }
        self.current_indent_level: int = 0
        self.line_number: int = 0
        self.indent_size: int = 0  # Detected size of first indent (spaces or 1 for tab)
        self.indent_type: str = '' # 'spaces' or 'tab'

    def _fatal_error(self, message: str):
        """Raises a fatal compilation error."""
        raise ValueError(f"Althtml Compile Error (Line {self.line_number}): {message}")

    def _get_indent_level(self, line: str) -> int:
        """
        Calculates the indentation level of a line.
        Detects indent size/type on the first indented line.
        Handles mixed indentation based on detected type/size.
        """
        match = re.match(r"^\s*", line)
        leading_whitespace = match.group(0) if match else ""

        if not leading_whitespace:
            return 0

        if self.indent_size == 0:
            # Detect indent type and size on first indented line
            if leading_whitespace.startswith('\t'):
                self.indent_type = 'tab'
                self.indent_size = 1 # Each tab is one level
            elif leading_whitespace.startswith(' '):
                self.indent_type = 'spaces'
                self.indent_size = len(leading_whitespace) # Size is the number of spaces
            else:
                 return 0 # Should not happen

            if self.indent_size == 0: return 0 # Avoid division by zero

        # Calculate level based on detected type
        if self.indent_type == 'tab':
            if not re.match(r"^\t+$", leading_whitespace):
                 print(f"Warning: Line {self.line_number}: Mixed indentation detected (tabs expected).")
                 # Attempt recovery: count tabs primarily
                 return leading_whitespace.count('\t')
            return len(leading_whitespace) # Number of tabs
        else: # spaces
            if not re.match(r"^ +$", leading_whitespace):
                 print(f"Warning: Line {self.line_number}: Mixed indentation detected (spaces expected).")
                 # Attempt recovery: count space groups primarily
                 # Ensure indent_size is positive before division
                 if self.indent_size > 0:
                     return len(leading_whitespace) // self.indent_size
                 else:
                      # This case should ideally not be reached if indent_size was detected correctly
                      # Or if the first line had no indent. Handle defensively.
                      print(f"Warning: Line {self.line_number}: Indent size is zero or negative, cannot calculate level accurately.")
                      return 0 # Fallback to level 0

            # Check consistency only if indent_size is positive
            if self.indent_size > 0 and len(leading_whitespace) % self.indent_size != 0:
                 self._fatal_error(f"Inconsistent space indentation. Expected multiple of {self.indent_size} spaces.")

            # Calculate level, handle potential division by zero if indent_size wasn't set
            return len(leading_whitespace) // self.indent_size if self.indent_size > 0 else 0


    def _close_tags(self, target_level: int):
        """Closes tags on the stack until the target indentation level is reached."""
        while self.tag_stack and self.tag_stack[-1]['indent_level'] >= target_level:
            closing_tag = self.tag_stack.pop()
            # Don't add closing tag for self-closed ones or !DOCTYPE
            if not closing_tag.get('self_closing', False) and closing_tag['tag_name'].lower() != '!doctype':
                indent = '  ' * closing_tag['indent_level'] # Optional: pretty print indent
                self.html_output += f"{indent}</{closing_tag['tag_name']}>\n"

    def _substitute_variables(self, text: str) -> str:
        """Performs variable substitution on a string segment."""
        substituted_text = text
        # Sort keys by length descending to match longer names first
        var_names = sorted(self.variables.keys(), key=len, reverse=True)
        for var_name in var_names:
            # Use regex with word boundaries to avoid partial matches
            # Ensure var_name is properly escaped for regex if needed, though simple names should be fine
            try:
                # Using simple replace as per spec (no word boundary check)
                substituted_text = substituted_text.replace(var_name, self.variables[var_name])
            except re.error:
                 # Fallback to simple replace if regex fails (e.g., bad var name)
                 substituted_text = substituted_text.replace(var_name, self.variables[var_name])
        return substituted_text

    def _parse_attributes(self, attr_string: str) -> str:
        """
        Parses attributes, handles ID shortcuts, collects bare words as classes,
        and performs variable substitution.
        Returns the processed HTML attribute string (e.g., ' class="active" id="user-123"').
        """
        if not attr_string:
            return ''

        other_attrs = '' # Store attributes like name=value, data-*, etc.
        id_value = ''
        explicit_classes = [] # Classes from class="val1 val2"
        implicit_classes = [] # Bare words treated as classes

        # Regex to split by space, respecting quotes
        tokens = re.findall(r'(?:[^\s"]+|"[^"]*")+', attr_string)

        for token in tokens:
            token = self._substitute_variables(token) # Substitute variables in the token itself first

            if token.startswith('#'):
                # ID Shortcut - substitute variables is already done
                id_value += token[1:]
            elif '=' in token:
                # Standard attribute name=value or name="value"
                parts = token.split('=', 1)
                name = parts[0]
                value = parts[1]
                # Remove quotes if present, handle escaped quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1].replace('\\"', '"')

                substituted_value = value # Value after initial token substitution

                # Basic escaping for the attribute value itself in HTML output
                escaped_value = substituted_value.replace('"', '&quot;')

                if name.lower() == 'class':
                    # Collect explicitly defined classes
                    explicit_classes.extend(escaped_value.split())
                else:
                    # Add other attributes directly
                    other_attrs += f' {name}="{escaped_value}"' # Always quote attribute values
            else:
                # Treat as implicit class name as per user request
                implicit_classes.append(token)


        # Combine classes
        all_classes = implicit_classes + explicit_classes
        class_string = ""
        if all_classes:
             # Remove duplicates while preserving order (simple approach)
             unique_classes = []
             for cls in all_classes:
                 if cls not in unique_classes:
                     unique_classes.append(cls)
             class_string = f' class="{" ".join(unique_classes)}"'


        # Combine ID
        id_string = ""
        if id_value:
            # Basic escaping for the final ID value
            escaped_id = id_value.replace('"', '&quot;')
            id_string = f' id="{escaped_id}"'

        return id_string + class_string + other_attrs # Order: id, class, others


    def _process_line(self, line_content: str, indent_level: int, lines: List[str], current_index: int) -> int:
        """
        Processes a single line of althtml code (content already trimmed).
        Returns the number of lines consumed.
        """
        self.line_number = current_index + 1 # For error reporting

        # --- Strip inline comment FIRST ---
        comment_index = line_content.find('#//')
        if comment_index != -1:
            # Check if the comment is inside quotes - basic check
            in_quotes = False
            quote_char = None
            for i in range(comment_index):
                char = line_content[i]
                if char in ('"', "'") and (i == 0 or line_content[i-1] != '#\\'):
                    if not quote_char:
                        quote_char = char
                        in_quotes = True
                    elif quote_char == char:
                        quote_char = None
                        in_quotes = False
            if not in_quotes:
                line = line_content[:comment_index].rstrip() # Remove comment and trailing space
            else:
                line = line_content # Comment is inside quotes, keep it
        else:
            line = line_content # No comment found


        # --- Handle Indentation ---
        if indent_level > self.current_indent_level + 1:
            self._fatal_error(f"Invalid indentation increase. Went from level {self.current_indent_level} to {indent_level}.")

        # Close tags if indent level decreases *before* processing line
        if indent_level < self.current_indent_level:
             self._close_tags(indent_level)

        # If indent level stayed same, close previous tag of same level *before* processing
        if indent_level == self.current_indent_level and self.tag_stack and self.tag_stack[-1]['indent_level'] == indent_level:
             self._close_tags(indent_level)

        # Update current level *after* potential closing, *before* processing line content
        self.current_indent_level = indent_level
        output_indent = '  ' * indent_level # Optional: pretty print indent

        # --- Skip Empty Lines (after comment removal) ---
        if not line:
            # Even if line is empty, indentation might have closed tags above
            return 1 # Consume 1 line

        # --- Handle Keywords: set, :macro ---
        if line.startswith('set '):
            consumed = self._handle_set(line, indent_level, lines, current_index)
            return consumed
        if line.startswith(':macro '):
            consumed = self._handle_macro_definition(line, indent_level, lines, current_index)
            return consumed

        # --- Handle Macro Invocation: @ ---
        if line.startswith('@'):
            self._handle_macro_invocation(line, indent_level)
            return 1 # Consume 1 line

        # --- Handle Macro Call: ! ---
        if line.startswith('!'):
            consumed = self._handle_macro_call(line, indent_level, lines, current_index)
            return consumed

        # --- Handle Explicit Text Line: | ---
        # Check for lines starting *only* with | (after stripping comments)
        if line.startswith('|'):
            text_content = line[1:].lstrip() # Preserve leading space after |
            substituted_text = self._substitute_variables(text_content)
            # Add text indented relative to the *parent* tag
            parent_indent_level = self.tag_stack[-1]['indent_level'] if self.tag_stack else -1
            text_indent_str = '  ' * (parent_indent_level + 1)
            self.html_output += f"{text_indent_str}{substituted_text}\n"
            return 1 # Consumed 1 line

        # --- SPECIAL HANDLING FOR 'raw' DIRECTIVE (block) ---
        if line == 'raw':
            # Get the block content
            raw_block_lines = self._get_block_lines(indent_level, lines, current_index)
            # Dedent the raw content
            dedented_content = self._dedent_block(raw_block_lines, indent_level + 1)
            # Output dedented content literally (no variable substitution)
            parent_indent_level = self.tag_stack[-1]['indent_level'] if self.tag_stack else -1
            raw_indent_str = '  ' * (parent_indent_level + 1)
            for content_line in dedented_content:
                 self.html_output += raw_indent_str + content_line # Includes original line ending
            return 1 + len(raw_block_lines) # Consumed 'raw' line + block lines
        # --- END SPECIAL HANDLING FOR 'raw' DIRECTIVE (block) ---

        # --- SPECIAL HANDLING FOR 'raw ' DIRECTIVE (line) ---
        if line.startswith('raw '):
            text_content = line[4:] # Get content after 'raw '
            # Output literally, no variable substitution
            parent_indent_level = self.tag_stack[-1]['indent_level'] if self.tag_stack else -1
            raw_indent_str = '  ' * (parent_indent_level + 1)
            self.html_output += f"{raw_indent_str}{text_content}\n"
            return 1 # Consumed 1 line
        # --- END SPECIAL HANDLING FOR 'raw ' DIRECTIVE (line) ---

        # --- SPECIAL HANDLING FOR 'raw@' DIRECTIVE (block) ---
        if line == 'raw@':
            # Get the block content
            raw_block_lines = self._get_block_lines(indent_level, lines, current_index)
            # Dedent the raw content
            dedented_content_lines = self._dedent_block(raw_block_lines, indent_level + 1)
            # Join lines, THEN substitute variables
            raw_text = "".join(dedented_content_lines)
            substituted_text = self._substitute_variables(raw_text)
            # Output substituted content, indented relative to parent
            parent_indent_level = self.tag_stack[-1]['indent_level'] if self.tag_stack else -1
            raw_indent_str = '  ' * (parent_indent_level + 1)
            # Add indent to each line of the potentially multi-line substituted text
            for output_line in substituted_text.splitlines(keepends=True):
                 self.html_output += raw_indent_str + output_line
            # Ensure a final newline if the original content didn't end with one but wasn't empty
            if substituted_text and not self.html_output.endswith('\n'):
                 self.html_output += '\n'
            return 1 + len(raw_block_lines) # Consumed 'raw@' line + block lines
        # --- END SPECIAL HANDLING FOR 'raw@' DIRECTIVE (block) ---

        # --- SPECIAL HANDLING FOR 'raw@ ' DIRECTIVE (line) ---
        if line.startswith('raw@ '):
            text_content = line[5:] # Get content after 'raw@ '
            # Substitute variables, then output literally
            substituted_text = self._substitute_variables(text_content)
            parent_indent_level = self.tag_stack[-1]['indent_level'] if self.tag_stack else -1
            raw_indent_str = '  ' * (parent_indent_level + 1)
            self.html_output += f"{raw_indent_str}{substituted_text}\n"
            return 1 # Consumed 1 line
        # --- END SPECIAL HANDLING FOR 'raw@ ' DIRECTIVE (line) ---


        # --- Handle Tags and Implicit Text ---
        tag_match = re.match(r"^(<[a-zA-Z0-9_-]+|[a-zA-Z0-9_-]+)(>?)\s*(.*)", line) # Capture rest after tag+>
        pipe_index = line.find('|') # Find pipe in the potentially comment-stripped line

        tag_name = ''
        is_self_closing = False
        line_remainder = line # Default if no tag match
        attr_str = ''
        text_content = ''
        is_implicit_text = False

        if tag_match:
            tag_name = tag_match.group(1)
            is_self_closing = tag_match.group(2) == '>'
            line_remainder = tag_match.group(3) # Everything after tag and optional '>'

            # Check for pipe within the remainder
            pipe_in_remainder_index = line_remainder.find('|')

            if pipe_in_remainder_index > -1:
                 # Pipe exists in the remainder
                 attr_str = line_remainder[:pipe_in_remainder_index].strip()
                 text_content = line_remainder[pipe_in_remainder_index + 1:].lstrip() # Preserve leading space after |
            else:
                 # No pipe, remainder is attributes
                 attr_str = line_remainder.strip()

        else:
            # No tag match, not starting with '|', not raw/raw@ directives, treat as implicit text
            is_implicit_text = True
            text_content = line # Use the whole (comment-stripped) line

        # --- Process as Tag or Text ---
        if tag_name:
            # --- Standard Tag Processing ---
            attributes = self._parse_attributes(attr_str)
            self.html_output += f"{output_indent}<{tag_name}{attributes}{' /' if is_self_closing else ''}>\n"

            if not is_self_closing:
                # Push onto stack BEFORE processing potential text content
                self.tag_stack.append({'tag_name': tag_name, 'indent_level': indent_level, 'self_closing': False})
                if text_content:
                    # Explicit text after | - preserve whitespace, substitute vars
                    substituted_text = self._substitute_variables(text_content)
                    # Add text indented appropriately inside the new tag (parent indent + 1)
                    self.html_output += f"{output_indent}  {substituted_text}\n"

            elif text_content:
                 # Text after | on a self-closing tag - normally ignored
                 pass
            # --- End Standard Tag Processing ---

        elif is_implicit_text:
            # Handle implicit text (no tag detected on the line, not starting with |)
            processed_text = ''
            # Check original text_content (comment-stripped line) for quotes
            if text_content.startswith('"') and text_content.endswith('"'):
                 # Quoted implicit text: remove quotes, preserve internal whitespace
                 processed_text = text_content[1:-1]
            else:
                 # Unquoted implicit text: collapse whitespace
                 processed_text = ' '.join(text_content.split())

            # Substitute variables
            substituted_text = self._substitute_variables(processed_text)

            # Add text indented relative to the *parent* tag
            parent_indent_level = self.tag_stack[-1]['indent_level'] if self.tag_stack else -1
            # Text should be indented one level deeper than parent
            text_indent_str = '  ' * (parent_indent_level + 1)
            self.html_output += f"{text_indent_str}{substituted_text}\n"

        return 1 # Consumed 1 line

    def _handle_set(self, line: str, indent_level: int, lines: List[str], current_index: int) -> int:
        """Handles the 'set' keyword for variable definition."""
        # line already has comment stripped by _process_line
        parts = line[4:].split('=', 1) # Split only on the first '='
        var_name = parts[0].strip()
        if not var_name:
            self._fatal_error("Variable name missing after 'set'.")

        if len(parts) > 1:
            # Inline assignment: set var = "value"
            value = parts[1].strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('\\"', '"')
            else:
                self._fatal_error(f"Inline set value for '{var_name}' must be enclosed in double quotes.")
            self.variables[var_name] = value
            return 1 # Consumed 1 line
        else:
            # Block assignment: set var \n ...block...
            block_lines_raw = self._get_block_lines(indent_level, lines, current_index)
            if not block_lines_raw:
                self.variables[var_name] = "" # Set to empty string if block is empty
                return 1 # Consumed only the 'set' line

            # Find first non-comment/empty line in the raw block
            first_real_line_index = 0
            while first_real_line_index < len(block_lines_raw) and \
                  (not block_lines_raw[first_real_line_index].strip() or \
                   block_lines_raw[first_real_line_index].strip().startswith('#//')):
                first_real_line_index += 1

            if first_real_line_index == len(block_lines_raw): # Block only comments/empty
                self.variables[var_name] = "" # Treat as empty block
                return 1 + len(block_lines_raw)


            first_line_trimmed = block_lines_raw[first_real_line_index].strip()

            if first_line_trimmed == 'raw':
                # Raw block
                # Need to dedent starting from the line *after* 'raw'
                start_index_for_dedent = first_real_line_index + 1
                raw_content_lines = self._dedent_block(block_lines_raw[start_index_for_dedent:], indent_level + 1)
                self.variables[var_name] = "".join(raw_content_lines) # Join without adding extra newlines
            else:
                # HTML Fragment block - Compile the block in isolation
                fragment_compiler = AlthtmlCompiler()
                # Pass existing definitions for substitution within the fragment
                fragment_compiler.variables = self.variables.copy()
                fragment_compiler.macros = self.macros.copy() # Shallow copy ok? Deepcopy if macros modify state internally
                # Dedent block lines for sub-compiler (use the original raw block)
                dedented_lines = self._dedent_block(block_lines_raw, indent_level + 1)
                # Compile the fragment
                self.variables[var_name] = fragment_compiler.compile("".join(dedented_lines)) # Join without adding extra newlines

            return 1 + len(block_lines_raw) # Consumed 'set' line + block lines

    def _handle_macro_definition(self, line: str, indent_level: int, lines: List[str], current_index: int) -> int:
        """Handles the ':macro' keyword for macro definition."""
        # line already has comment stripped
        name_part = line[7:].strip()
        if not name_part:
            self._fatal_error("Macro name missing after ':macro'.")

        is_arg_macro = name_part.startswith('!')
        macro_name = name_part[1:] if is_arg_macro else name_part
        if not macro_name:
            self._fatal_error("Macro name missing after ':macro !'." if is_arg_macro else "Macro name missing after ':macro'.")

        definition_lines_raw = self._get_block_lines(indent_level, lines, current_index)
        # Dedent the macro body to be relative to level 0 for storage
        definition_lines = self._dedent_block(definition_lines_raw, indent_level + 1)

        # Simple check for argument count
        arg_count = 0
        if is_arg_macro:
            arg_regex = re.compile(r'@(\d+)')
            max_arg = -1
            for def_line in definition_lines:
                 # Strip comments from definition lines before checking args
                 clean_def_line = def_line.split('#//')[0]
                 matches = arg_regex.findall(clean_def_line)
                 for match in matches:
                     max_arg = max(max_arg, int(match))
            arg_count = max_arg + 1 if max_arg > -1 else 0


        self.macros[macro_name] = {'definition_lines': definition_lines, 'is_arg_macro': is_arg_macro, 'arg_count': arg_count}
        return 1 + len(definition_lines_raw) # Consumed ':macro' line + block lines

    def _handle_macro_invocation(self, line: str, indent_level: int):
        """Handles macro invocation using '@'."""
        # line already has comment stripped
        macro_name = line[1:].strip()
        if not macro_name:
            self._fatal_error("Macro name missing after '@'.")

        macro = self.macros.get(macro_name)
        if not macro:
            self._fatal_error(f"Undefined macro invoked: '@{macro_name}'.")
        if macro['is_arg_macro']:
            self._fatal_error(f"Cannot invoke argument macro '@{macro_name}' using '@'. Use '!{macro_name}'.")

        # Compile the macro definition lines in isolation
        macro_compiler = AlthtmlCompiler()
        macro_compiler.variables = self.variables.copy()
        macro_compiler.macros = self.macros.copy() # Pass macro defs too

        compiled_macro = macro_compiler.compile("".join(macro['definition_lines'])) # Join without adding extra newlines

        # Add the compiled output, adjusting indentation
        output_indent_str = '  ' * indent_level
        # Indent non-empty lines of the compiled output
        indented_output = "\n".join([f"{output_indent_str}{l}" if l else "" for l in compiled_macro.splitlines()])
        # Avoid double newlines if compiled_macro already ends with one
        self.html_output += indented_output
        if compiled_macro and not indented_output.endswith('\n'): # Add newline if output wasn't empty
             self.html_output += "\n"


    def _handle_macro_call(self, line: str, indent_level: int, lines: List[str], current_index: int) -> int:
        """Handles macro calls using '!'."""
        # line already has comment stripped
        macro_name = line[1:].strip()
        if not macro_name:
            self._fatal_error("Macro name missing after '!'.")

        macro = self.macros.get(macro_name)
        if not macro:
            self._fatal_error(f"Undefined macro called: '!{macro_name}'.")
        if not macro['is_arg_macro']:
            self._fatal_error(f"Cannot call simple macro '!{macro_name}' using '!'. Use '@{macro_name}'.")

        # 1. Get argument blocks
        arg_blocks_raw = self._get_argument_blocks(indent_level, lines, current_index)

        if len(arg_blocks_raw) != macro['arg_count']:
            self._fatal_error(f"Macro '!{macro_name}' expected {macro['arg_count']} arguments, but received {len(arg_blocks_raw)}.")

        # 2. Process/Compile arguments
        args: List[str] = []
        for i, arg_block in enumerate(arg_blocks_raw):
            if not arg_block:
                args.append("")
                continue

            # Find first real line (ignoring comments/empty)
            first_real_line_index = 0
            while first_real_line_index < len(arg_block) and \
                  (not arg_block[first_real_line_index].strip() or \
                   arg_block[first_real_line_index].strip().startswith('#//')):
                first_real_line_index += 1

            if first_real_line_index == len(arg_block): # Block was only comments/empty
                 args.append("")
                 continue

            first_real_line = arg_block[first_real_line_index]
            # Strip comment from the first real line before checking its structure
            first_real_line_content = first_real_line.split('#//')[0].rstrip()
            first_real_line_trimmed = first_real_line_content.strip()


            # Check if it looks like a tag/keyword start on the first *real* line's content
            is_simple_text = not re.match(r"^\s*([a-zA-Z0-9_-]+|>|<[a-zA-Z0-9_-]+|@|!|:|set)", first_real_line_content) \
                             or first_real_line_trimmed.startswith('|')

            # Check if block contains only one real line + comments/empty
            is_single_real_line = True
            for j in range(first_real_line_index + 1, len(arg_block)):
                 if arg_block[j].strip() and not arg_block[j].strip().startswith('#//'):
                     is_single_real_line = False
                     break

            if is_simple_text and is_single_real_line:
                # Simple text argument (potentially with |)
                text = first_real_line_trimmed # Use content stripped of comment
                if text.startswith('|'):
                    text = text[1:].lstrip()
                args.append(self._substitute_variables(text)) # Substitute variables
            else:
                # Structural argument - compile it
                arg_compiler = AlthtmlCompiler()
                arg_compiler.variables = self.variables.copy()
                arg_compiler.macros = self.macros.copy()
                # Dedent the *whole* original block for compilation
                dedented_lines = self._dedent_block(arg_block, indent_level + 1)
                args.append(arg_compiler.compile("".join(dedented_lines))) # Join without adding extra newlines

        # 3. Substitute arguments into macro definition
        # Strip comments from definition lines before substitution
        clean_definition_lines = [l.split('#//')[0].rstrip() for l in macro['definition_lines']]
        substituted_definition = "\n".join(clean_definition_lines) # Use newline for joining template lines

        # Replace arguments carefully, maybe from highest index to lowest
        for i in range(macro['arg_count'] -1, -1, -1):
             substituted_definition = substituted_definition.replace(f"@{i}", args[i])


        # 4. Compile the substituted definition
        macro_compiler = AlthtmlCompiler()
        macro_compiler.variables = self.variables.copy()
        macro_compiler.macros = self.macros.copy() # Pass definitions for nested calls
        compiled_macro = macro_compiler.compile(substituted_definition) # Pass as single string

        # 5. Add compiled output with correct indentation
        output_indent_str = '  ' * indent_level
        indented_output = "\n".join([f"{output_indent_str}{l}" if l else "" for l in compiled_macro.splitlines()])
        self.html_output += indented_output
        if compiled_macro and not indented_output.endswith('\n'): # Add newline if output wasn't empty
             self.html_output += "\n"


        # Calculate consumed lines
        consumed = 1 # The '!' line itself
        for block in arg_blocks_raw:
            consumed += len(block)
        return consumed

    # --- Helper Methods ---

    def _get_block_lines(self, parent_indent_level: int, lines: List[str], parent_index: int) -> List[str]:
        """Extracts lines belonging to a block indented relative to a parent line."""
        block_lines: List[str] = []
        i = parent_index + 1
        while i < len(lines):
            line = lines[i]
            # Need to get indent level first to check against parent
            level = self._get_indent_level(line) # Use original line for indent

            # Strip comment *after* getting indent, before checking content
            line_content = line.split('#//')[0].rstrip()

            if level > parent_indent_level:
                block_lines.append(line) # Add original line to preserve comments/indent
            elif level <= parent_indent_level and line_content: # Non-empty content line ends block
                break
            elif not line_content: # Keep empty lines if they don't break indent
                 if block_lines: # Only keep empty lines inside a block
                     block_lines.append(line)
                 # If empty line is first potential line of block, ignore it unless needed?
            else: # Line breaks the block structure (lower indent or comment at wrong level?)
                 break
            i += 1
        return block_lines


    def _get_argument_blocks(self, call_indent_level: int, lines: List[str], call_index: int) -> List[List[str]]:
        """
        Extracts argument blocks following a '!' macro call.
        Assumes arguments are consecutive blocks starting at the next indent level.
        """
        arg_blocks: List[List[str]] = []
        current_arg_block: List[str] = []
        i = call_index + 1
        expected_indent = call_indent_level + 1
        parsing_args = False # Flag to indicate if we are currently inside any arg block structure

        while i < len(lines):
            line = lines[i]
            level = self._get_indent_level(line) # Use original line for indent level
            line_content = line.split('#//')[0].rstrip() # Content without comment
            line_trimmed_content = line_content.strip() # Trimmed content

            if level > call_indent_level:
                # Line is indented potentially as part of an argument
                if level == expected_indent and line_trimmed_content:
                    # Line is at the expected level and has content
                    # Potential start of a new argument block OR continuation if already parsing
                    if current_arg_block and parsing_args: # Finish previous block, start new one
                         arg_blocks.append(current_arg_block)
                    current_arg_block = [line] # Start new block with original line
                    parsing_args = True # We are now officially parsing args
                elif parsing_args:
                     # Line is deeper than expected_indent or is comment/empty - belongs to current block
                     current_arg_block.append(line) # Add original line
                # else: line is indented but not at expected level and we haven't started parsing - ignore

            elif parsing_args:
                 # Indent level dropped or is equal, and we were parsing args -> end of all args
                 break
            elif not line_trimmed_content: # Allow empty lines between call and first arg
                 pass
            else: # Line is not indented enough and we haven't started - means no args or done
                 break

            i += 1

        # Add the last collected argument block
        if current_arg_block and parsing_args:
            arg_blocks.append(current_arg_block)

        return arg_blocks


    def _get_indent_chars(self, level: int) -> str:
        """Gets the whitespace string for a given indent level."""
        if level < 0: level = 0 # Safety check
        if self.indent_size == 0 and level > 0: return "" # Indent not detected yet
        if self.indent_type == 'tab':
            return '\t' * level
        elif self.indent_type == 'spaces':
            # Ensure indent_size is positive
            size = self.indent_size if self.indent_size > 0 else 1
            return ' ' * (level * size)
        else: # level == 0 or indent not detected
             return ""


    def _dedent_block(self, block_lines: List[str], base_indent_level: int) -> List[str]:
        """Dedents a block of lines relative to a base indent level. Returns lines WITH original line endings."""
        if not block_lines: return []

        # Try to get base indent chars, infer if necessary
        base_indent_chars = self._get_indent_chars(base_indent_level)
        inferred = False
        if not base_indent_chars and base_indent_level > 0:
             # Find first non-empty, non-comment line to infer from
             first_real_line = next((line for line in block_lines if line.strip() and not line.strip().startswith('#//')), None)
             if first_real_line:
                 match = re.match(r"^\s*", first_real_line)
                 leading_whitespace = match.group(0) if match else ""
                 if leading_whitespace:
                    # This assumes the first line *is* at the base_indent_level
                    base_indent_chars = leading_whitespace
                    inferred = True
                 else:
                     # First real line has no indent? Cannot dedent.
                     print(f"Warning: Cannot reliably dedent block - first line has no indent.")
                     return block_lines # Return original lines with endings
             else: # Block only contains comments/empty lines
                  return block_lines # Return original lines


        dedented: List[str] = []
        for i, line in enumerate(block_lines):
            # Preserve comments and empty lines relative to structure
            original_line_trimmed = line.strip()
            is_comment = original_line_trimmed.startswith('#//')
            is_empty = not original_line_trimmed

            if line.startswith(base_indent_chars):
                # Dedent the line content, keep original line ending
                dedented.append(line[len(base_indent_chars):])
            elif is_empty:
                 # Keep empty lines as they were (including just newline)
                 dedented.append(line)
            elif is_comment:
                 # Keep comment lines, but dedent them if possible
                 if line.startswith(base_indent_chars):
                      dedented.append(line[len(base_indent_chars):])
                 else: # Comment has less indent than expected base, keep as is
                      dedented.append(line)
            elif inferred:
                 # If we inferred indent, maybe this line just has less? Fallback.
                 dedented.append(line.lstrip()) # Remove all leading space as best guess
            else:
                # This indicates an inconsistent indent within the block
                print(f"Warning: Line {self.line_number - len(block_lines) + i + 1}: Unexpected indentation during dedent.")
                dedented.append(line) # Return original line

        return dedented

    def clear_macro_variables(self) -> None:
        self.variables = {}
        self.macros = {}

    def compile(self, source: str) -> str:
        """Compiles althtml source code to HTML."""
        # Reset state for fresh compilation
        self.html_output = ''
        self.tag_stack = []
        self.current_indent_level = 0
        self.line_number = 0
        self.indent_size = 0 # Reset indent detection
        self.indent_type = ''


        lines = source.splitlines(keepends=True) # Keep line endings for raw blocks
        i = 0
        while i < len(lines):
            self.line_number = i + 1 # Update line number for accurate errors
            line = lines[i]
            # Use rstrip to remove trailing whitespace but keep leading for indent calc
            original_line_content_for_indent = line.rstrip('\r\n')
            original_line_trimmed = line.strip() # Trimmed version for comment/empty check

            # Skip comment-only lines at the top level FIRST
            if original_line_trimmed.startswith('#//') or not original_line_trimmed:
                i += 1
                continue

            # Calculate indent level using the original line (with leading ws)
            indent_level = self._get_indent_level(original_line_content_for_indent)

            # Process the *content* part of the line (already trimmed)
            # Pass the trimmed content to _process_line
            consumed_lines = self._process_line(original_line_trimmed, indent_level, lines, i)
            i += consumed_lines

        # Close any remaining open tags AFTER the loop finishes
        self._close_tags(0)

        # Simple check for required root 'html' tag
        # if not self.html_output.strip().startswith('<html'):
        #      print("Warning: Output does not start with an <html> tag.")

        # Remove trailing newline from final output if present
        if self.html_output.endswith('\n'):
             self.html_output = self.html_output[:-1]

        return self.html_output
