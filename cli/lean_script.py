#!/usr/bin/env python3
"""Remove match arms for deleted commands from commands.rs"""
import re, sys

with open("src/commands.rs", "r") as f:
    lines = f.readlines()

# Track brace depth and identify match arm boundaries
# We work on the main parse_command function

# Find parse_command function
func_lines_start = None
func_body_start = None
brace_depth = 0

for i, line in enumerate(lines):
    if "pub fn parse_command" in line:
        func_lines_start = i
    if func_lines_start is not None and func_body_start is None:
        # Find the first opening brace of the function
        if '{' in line:
            func_body_start = i
            brace_depth = line.count('{') - line.count('}')

# If the brace is on a subsequent line
if func_body_start and brace_depth <= 0:
    for i in range(func_body_start + 1, len(lines)):
        brace_depth += lines[i].count('{') - lines[i].count('}')
        if brace_depth > 0:
            func_body_start = i
            break

print(f"parse_command: declaration at line {func_lines_start+1}, body starts at line {func_body_start+1}")

# Now find the main match block inside the function
# It starts with `let result = match cmd {` or similar
match_start = None
match_brace_depth = 0

for i in range(func_body_start + 1, len(lines)):
    stripped = lines[i].strip()
    # Look for a match on `cmd` or `rest[0]`
    if re.match(r'^\s*(let\s+\w+\s*=\s*)?match\s+\w', stripped):
        match_start = i
        match_brace_depth = stripped.count('{') - stripped.count('}')
        # Read forward to find the match body's opening brace
        for j in range(i + 1, len(lines)):
            match_brace_depth += lines[j].count('{') - lines[j].count('}')
            if match_brace_depth > 0:
                match_start = j
                break
        break

print(f"Main match starts at line {match_start+1}" if match_start else "No main match found?")

# Now read the main match body and identify match arms
# Top-level match arms start at column ~8 (two tabs)
# Let me find the indent of the first arm
first_arm_indent = None
for i in range(match_start + 1 if match_start else 0, len(lines)):
    stripped = lines[i].strip()
    if stripped.startswith('"') and '=>' in stripped:
        first_arm_indent = len(lines[i]) - len(lines[i].lstrip())
        break
    if stripped.startswith('|') and '=>' in stripped:
        first_arm_indent = len(lines[i]) - len(lines[i].lstrip())
        break

print(f"First arm indent: {first_arm_indent} spaces")

# Now identify all match arms in the main match at the first_arm_indent level
# and mark which are for removed commands

removed_arms = {
    "state", "drag", "keydown", "keyup", "inserttext", "insertText",
    "pdf", "swipe",
    "device", "device_list", "tree", "react_tree", "react_inspect",
    "react_renders_start", "react_renders_stop", "react_suspense",
    "diff_snapshot", "diff_url", "diff_screenshot",
    "screencast_start", "screencast_stop",
    "video_start", "video_stop",
    "getbyrole", "getbytext", "getbylabel", "getbyplaceholder",
    "getbyalttext", "getbytitle", "getbytestid",
    "geolocation", "timezone", "locale", "permissions",
    "confirm", "deny", "expose",
    "mousemove", "mousedown", "mouseup",
    "input_mouse", "input_keyboard", "input_touch",
    "window_new",
    "close",  # keep? no, close is still used
}

# Actually let me check which of these are in the main match
# I need to read through the match block and identify arms

# I'll use brace counting to find match arm boundaries
lines_to_delete = set()

# For the main match, I need to track braces
# A match arm at the top level ends either at:
# 1. A comma (for one-liners like "cmd" => Ok(...), )
# 2. The closing of a brace block, followed by the next arm at same indent
# 3. The end of the match block

# Let me trace through and find deleted cmd arms
current_arm_start = None
current_arm_cmd = None
arm_indent = first_arm_indent
match_ended = False

for i in range(match_start + 1 if match_start else 0, len(lines)):
    if match_ended:
        break
        
    line = lines[i]
    indent = len(line) - len(line.lstrip())
    stripped = line.strip()
    
    # Check if we've reached the end of the match block
    # The match concludes with a closing brace at arm_indent level
    if stripped == '}' and indent <= arm_indent:
        # This is the closing of the match block
        # Flush current arm
        current_arm_start = None
        current_arm_cmd = None
        match_ended = True
        continue
    
    # Check for new match arm: "cmd" => at arm_indent
    # Also handle: "cmd1" | "cmd2" => at arm_indent
    arm_match = re.match(r'^(\s*)((?:"[^"]+"\s*(?:\|\s*)?)+)\s*=>', line)
    if arm_match:
        arm_ind = len(arm_match.group(1))
        arm_pattern = arm_match.group(2)
        
        if arm_ind <= first_arm_indent:
            # This is a top-level match arm
            # Extract all command names from the pattern
            cmds = re.findall(r'"([^"]+)"', arm_pattern)
            
            # Check if ANY of these commands is in the removed set
            is_removed = any(c in removed_arms for c in cmds)
            
            # Flush previous arm
            current_arm_start = i if is_removed else None
            current_arm_cmd = cmds[0] if cmds else None
            
            # If it's a one-liner, we can mark it now
            if '=>' in line and '{' not in line:
                if is_removed:
                    lines_to_delete.add(i)
                current_arm_start = None
                current_arm_cmd = None
                continue
            
            if is_removed:
                print(f"  Removing arm '{current_arm_cmd}' starting at line {i+1}")
        else:
            # Nested match arm - ignore
            pass
        continue
    
    # If we're tracking an arm to delete, mark this line
    if current_arm_start is not None:
        # Check if this line starts a new arm at the same level
        new_arm = re.match(r'^\s*"[^"]+"\s*=>', line)
        if new_arm and len(new_arm.group(0)) - len(new_arm.group(0).lstrip()) <= first_arm_indent:
            current_arm_start = None
            current_arm_cmd = None
            continue
        
        lines_to_delete.add(i)
        
        # Check if we've reached the end of the block
        # Brace depth tracked from the arm start
        pass

# This approach is brittle. Let me try a simpler one: 
# Just remove lines that are known to be part of deleted arms.
# I'll identify all the lines manually from the grep output.

# Actually, let me just use line ranges based on careful reading
print("\n=== Manually verified deletions ===")

# Let me look at each area and determine exact boundaries
# First let me read the critical sections

# Sniff flags (lines 294-304)
print(f"\nSniff flags: lines 295-304 (10 lines)")
for i in range(294, 305):
    print(f"  {i+1}: {lines[i].rstrip()}")

# State match arm (lines 347-354)
print(f"\nState arm: lines 347-354")
for i in range(346, 355):
    print(f"  {i+1}: {lines[i].rstrip()}")
