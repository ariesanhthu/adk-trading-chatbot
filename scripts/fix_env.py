"""Script để sửa format .env file (xóa dấu cách thừa)."""

import os
from pathlib import Path

# Đường dẫn đến .env
env_path = Path(__file__).parent.parent / ".env"

if not env_path.exists():
    print(f"❌ File .env không tồn tại tại: {env_path}")
    exit(1)

# Đọc file
with open(env_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Sửa các dòng có dấu cách thừa quanh dấu =
fixed_lines = []
for line in lines:
    # Sửa "BE_API = " thành "BE_API="
    if "BE_API" in line and "=" in line:
        # Tách key và value
        parts = line.split("=", 1)
        if len(parts) == 2:
            key = parts[0].strip()
            value = parts[1].strip()
            fixed_line = f"{key}={value}\n"
            fixed_lines.append(fixed_line)
            print(f"✅ Fixed: {line.strip()} → {fixed_line.strip()}")
        else:
            fixed_lines.append(line)
    else:
        fixed_lines.append(line)

# Ghi lại file
with open(env_path, "w", encoding="utf-8") as f:
    f.writelines(fixed_lines)

print(f"\n✅ Đã sửa file .env tại: {env_path}")
