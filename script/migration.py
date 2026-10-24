import sys
import os
import argparse
from alembic.config import Config
from alembic import command

def run_migrations():
    # 1. Cấu hình nhận tham số truyền vào (upgrade hoặc downgrade)
    parser = argparse.ArgumentParser(description="Alembic Migration Script")
    parser.add_argument(
        "action", 
        choices=["upgrade", "downgrade"], 
        default="upgrade", 
        nargs="?",
        help="Chọn 'upgrade' để nâng cấp hoặc 'downgrade' để hạ cấp database (Mặc định: upgrade)"
    )
    parser.add_argument(
        "--revision", 
        default=None, 
        help="Mã revision cụ thể (Ví dụ: base, -1, eae66b6e306a). Nếu upgrade mặc định là 'head', downgrade mặc định là '-1'"
    )
    args = parser.parse_args()

    # 2. Xác định đường dẫn tới file alembic.ini
    base_dir = os.path.abspath(os.path.dirname(__file__) + "/..")
    ini_path = os.path.join(base_dir, "alembic.ini")
    
    if not os.path.exists(ini_path):
        print(f"❌ LỖI: Không tìm thấy file cấu hình Alembic tại: {ini_path}")
        sys.exit(1)
        
    alembic_cfg = Config(ini_path)
    
    try:
        if args.action == "upgrade":
            target_rev = args.revision or "head"
            print(f"--- [MIGRATION] Đang nâng cấp DB lên revision: {target_rev} ---")
            command.upgrade(alembic_cfg, target_rev)
            print("✅ [MIGRATION] Nâng cấp Database THÀNH CÔNG!")
            
        elif args.action == "downgrade":
            # Nếu không truyền revision cụ thể khi downgrade, mặc định sẽ lùi lại 1 phiên bản (-1)
            target_rev = args.revision or "-1"
            print(f"--- [MIGRATION] Đang hạ cấp DB về revision: {target_rev} ---")
            command.downgrade(alembic_cfg, target_rev)
            print("✅ [MIGRATION] Hạ cấp Database THÀNH CÔNG!")
            
    except Exception as e:
        print(f"❌ LỖI trong quá trình thực thi migration ({args.action}): {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migrations()
