# Althtml Language Specification (v3)

This file describes althtml, a templating language that compiles to HTML. It uses indentation for structure and implements compile-time variables and macros for generating HTML content.

## 1. Indentation & Hierarchy

Indentation determines the nesting hierarchy of elements.

- **Indentation Unit:** Can be spaces or tabs. Mixed indentation is permitted, but consistent indentation (e.g., 4 spaces or 1 tab per level) is recommended for readability. The parser determines levels based on changes in leading whitespace and detects the unit (tab or number of spaces) on the first indented line.
- **Hierarchy:** Each increase in indentation level creates a child element relative to the parent element defined by the previous, less-indented line. A decrease signifies closing the nested element(s) back to the corresponding parent level.
- **Validity:** An indentation increase is only valid if it is exactly one level deeper than its parent element's level. Empty lines do not affect indentation validation for subsequent lines.
- **Root:** Lines with no indentation (level 0) are at the root level.

**Example Hierarchy:**

```althtml
html
    head
        title | My Page
    body
        div
            p

        footer
```

Translates to:

```html
<html>
  <head>
    <title>My Page</title>
  </head>
  <body>
    <div>
      <p></p>
    </div>
    <footer></footer>
  </body>
</html>
```

## 2. Comments Syntax

Use `#//` for comments.

- **Behavior:** The `#//` and all subsequent characters on that line are ignored by the compiler before parsing the line's content (tags, attributes, text, etc.).
- **Placement:** Comments can start at the beginning of a line or follow code/text on the same line.

**Example:**

```althtml
#// This is a full-line comment.
div class="container" #// This comment is stripped before parsing attributes.
    p | Hello #// This comment is also ignored.
```

## 3. Tags & Elements

Lines generally start with an HTML tag name, a custom tag name, a keyword (`set`, `:macro`, `raw`, `raw@`), a macro invocation (`@`), a macro call (`!`), or text content (`|` or implicit).

- **Standard HTML Tags:** Any standard HTML tag name (e.g., `div`, `p`, `span`, `script`, `!DOCTYPE`) can be used.
- **Custom Tags:** Tag names starting with `<` (e.g., `<my-component`) are treated as custom elements.
- **Self-Closing Tags:** Append `>` directly to the tag name (e.g., `img>`, `meta>`, `input>`) to create a self-closing tag (outputting `<tag ... />`). Tags without the trailing `>` are standard paired tags (outputting `<tag ...>...</tag>`).

**Example:**

```althtml
div
    img> src="logo.png" alt="My Image"
    br>
    <custom-element>
        span | Content
```

## 4. Attributes

Attributes follow the tag name on the same line, before any `|` character or comment (`#//`).

- **Syntax:** `name=value` or `name="value with spaces"`. Quotes (`"`) around values are delimiters and are not included in the output value, unless escaped (`\"`). Output attribute values are generally wrapped in quotes by the compiler for robustness (e.g., `name="value"`).
- **Implicit Classes:** Standalone words become CSS classes and are aggregated into the `class` attribute.
- **Explicit Classes:** Classes defined via `class="value1 value2"` are combined with implicit classes. Duplicates are removed.
- **ID Shortcut (`#`):** A token starting with `#` contributes to the element's `id`. The string following the `#` is used. Multiple `#` tokens concatenate their values. Variable substitution occurs within these tokens.

**Example:**

```althtml
set userId = "123"
set theme = "dark"

input> type="text" name="username" required
div btn theme class="extra" #user- #userId data-value="some \"quoted\" data"
```

**Output:**

```html
<div id="user-123" class="btn dark extra" data-value="some &quot;quoted&quot; data"></div>
```

## 5. Text Content

Text content can be added explicitly, implicitly, or via raw directives.

- **Explicit (`|`):** Text following a `|` character on the same line as a tag (or on a line starting only with `|`) is treated as literal text content. Whitespace and quotes within this text are preserved exactly as written. Variable substitution is performed.

**Example:**

```althtml
p | This is "literal text" for user.
```

**Output:**

```html
<p>This is "literal text" for user.</p>
```

- **Implicit/Default:** If a line starts with text that is not a recognized tag, keyword, or directive, it is treated as text content for its parent element. Whitespace in this text is collapsed (like standard HTML). Variable substitution is performed.

**Example:**

```althtml
p
    Some text for user.
```

**Output:**

```html
<p>Some text for user.</p>
```

## 6. Raw Directives (`raw`, `raw@`)

These directives output content literally without creating HTML tags themselves, indented relative to their parent.

- **`raw` (Block):** Outputs content literally. No variable substitution is performed.
- **`raw@` (Block):** Outputs content literally, but variable substitution is performed.

**Example:**

```althtml
div
    raw
        <script> let user = "user"; </script>
    raw@
        <script>let user = "username";</script>
```

## 7. Variables (`set`)

Variables are defined at compile time and hold string values.

- **Definition:**
  - Inline: `set <varname> = "string literal"`
  - Block (Raw String): `set <varname>` followed by an indented block starting with `raw`.
  - Block (HTML Fragment): `set <varname>` followed by an indented block containing althtml structure.

**Example:**

```althtml
set siteName = "My Cool Site"
set footerContent
    raw
        Copyright (c) 2025
        All rights reserved.

body
    p | Welcome to siteName
    footerContent
```

## 8. Macros (`:macro`)

Macros allow defining reusable althtml templates at compile time.

- **Definition:**
  - Simple Macros: `:macro <name>` followed by an indented block.
  - Argument Macros: `:macro !<name>` followed by an indented block using `@0`, `@1`, etc. for arguments.

**Example:**

```althtml
:macro basicCard
    div class="card shadow"

:macro !button
    button class="btn btn-@0"
        @1

body
    @basicCard
        p | Card Content

    !button
        primary
        | Click Me
```