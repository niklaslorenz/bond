# Issue: CSS Styling Audit

## Problem Description
The TUI uses a custom CSS file (`tui.css`) for styling, but it is not clear if:
- The styling is **consistent** across widgets.
- The styling is **responsive** and works well on different terminal sizes.
- The styling follows **best practices** for readability and user experience.

### Specific Issues
1. **Inconsistent Styling**: Different widgets (e.g., `ChatMessage`, `StatusBar`, `InputBar`) may have inconsistent colors, borders, or spacing.
2. **Poor Readability**: Text may be hard to read due to low contrast or small font sizes.
3. **Lack of Responsiveness**: The TUI may not adapt well to different terminal sizes.
4. **Unused or Redundant Styles**: The CSS file may contain styles that are no longer used.

## Current Implementation
The `tui.css` file is referenced in `BondTui`:
```python
CSS_PATH = str(Path(__file__).with_name("tui.css"))
```

However, its contents have not been analyzed for consistency or best practices.

## Proposed Solution
Audit the `tui.css` file to ensure:
1. **Consistency**: Styles are applied uniformly across widgets.
2. **Readability**: Text is legible and colors have sufficient contrast.
3. **Responsiveness**: The TUI adapts to different terminal sizes.
4. **Maintainability**: The CSS is well-organized and documented.

### Implementation Plan

#### 1. Review the Current CSS
Examine the `tui.css` file to identify:
- Global styles (e.g., colors, fonts).
- Widget-specific styles (e.g., `ChatMessage`, `StatusBar`).
- Responsive design rules.

#### 2. Define a Style Guide
Create a style guide for the TUI to ensure consistency:
- **Colors**:
  - Primary color for user messages.
  - Secondary color for assistant messages.
  - Status colors (e.g., red for errors, green for success).
- **Fonts**: Use a monospace font for code blocks.
- **Spacing**: Consistent padding and margins.
- **Borders**: Use borders to distinguish widgets.

Example style guide:
```css
/* Colors */
--user-message-color: #007acc;
--assistant-message-color: #6c757d;
--error-color: #dc3545;
--success-color: #28a745;

/* Fonts */
--font-family: "Consolas", "Monaco", monospace;

/* Spacing */
--padding: 1;
--margin: 1;

/* Borders */
--border-width: 1;
--border-color: #6c757d;
```

#### 3. Refactor the CSS
Update the `tui.css` file to follow the style guide:
```css
/* Global Styles */
App {
    background: #f8f9fa;
    color: #212529;
    font-family: var(--font-family);
}

/* Status Bar */
#status-bar {
    background: #e9ecef;
    color: #212529;
    padding: 0.5em;
    border-bottom: 1px solid #6c757d;
}

/* Chat Message */
ChatMessage {
    margin: var(--margin);
    padding: var(--padding);
    border-left: var(--border-width) solid var(--border-color);
}

ChatMessage.user {
    border-left-color: var(--user-message-color);
}

ChatMessage.assistant {
    border-left-color: var(--assistant-message-color);
}

/* Input Bar */
#input-layer {
    background: #e9ecef;
    padding: 0.5em;
    border-top: 1px solid #6c757d;
}

/* Scrollable Container */
ChatLog {
    scrollbar-gutter: stable;
}
```

#### 4. Test Responsiveness
Ensure the TUI works well on different terminal sizes:
- Test with a small terminal (e.g., 80x24).
- Test with a large terminal (e.g., 120x40).
- Verify that widgets resize correctly and text remains legible.

#### 5. Add Documentation
Document the CSS file to explain its purpose and usage:
```css
/*
 * TUI Styling for the Bond AI Agent
 * 
 * This file defines the styles for the Textual-based TUI.
 * It uses CSS variables for consistency and maintainability.
 * 
 * Global Styles:
 * - App: Base styles for the entire application.
 * - StatusBar: Styles for the status bar at the bottom.
 * - ChatMessage: Styles for chat messages (user/assistant).
 * - InputBar: Styles for the input field.
 * - ChatLog: Styles for the scrollable chat log.
 */
```

#### 6. Verify Contrast and Readability
Use a tool like [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/) to ensure text has sufficient contrast against its background.

#### 7. Test Edge Cases
Test edge cases such as:
- Long messages that wrap.
- Messages with mixed content (text, code blocks, tool results).
- Empty states (e.g., no messages in the chat log).

## Expected Outcome
- The `tui.css` file will be **consistent**, **readable**, and **responsive**.
- The TUI will provide a **polished user experience** across different terminal sizes.
- The CSS will be **well-documented** and **maintainable**.

## Additional Notes
- Use **CSS variables** to ensure consistency and make it easier to update styles.
- Consider using **Textual's dark mode** for better readability in low-light environments.
- Test the TUI on different platforms (e.g., Linux, macOS, Windows) to ensure cross-platform compatibility.
