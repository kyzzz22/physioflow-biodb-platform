# create_admin.py

import argparse
# 既存のデータベース接続コードやモデル定義をインポート
# (ここでは仮に `db_models.py` というファイルにまとまっていると仮定)
from psql import ensure_admin_user, Base, engine

def main():
    # コマンドライン引数のパーサーをセットアップ
    parser = argparse.ArgumentParser(
        description="Create or update a user to have admin privileges (for OAuth)."
    )
    parser.add_argument(
        "--email", 
        type=str, 
        required=True, 
        help="Google account email address for the admin user."
    )

    args = parser.parse_args()

    try:
        # 作成した関数を呼び出す
        admin_user = ensure_admin_user(email=args.email)
        
        print("\n--- Operation Summary ---")
        print(f"  ID: {admin_user['id']}")
        print(f"  Email: {admin_user['email']}")
        print(f"  Role: {admin_user['role']}")
        print("-------------------------")
        print("Operation completed successfully.")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # データベースのテーブルがなければ作成する
    Base.metadata.create_all(bind=engine)
    main()