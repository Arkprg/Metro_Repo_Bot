import pandas as pd
import sqlite3

path = ""

# فایل اکسل و برگه‌ی مورد نظر
excel_file = path + 'data.xlsx'
sheet_name = 'Sheet1'

# خواندن داده‌ها از اکسل به DataFrame با استفاده از pandas
df = pd.read_excel(excel_file, sheet_name=sheet_name)

# ایجاد اتصال به پایگاه داده SQLite (در صورت عدم وجود، فایل جدیدی ایجاد می‌شود)
sqlite_db = path + 'Person.db'
conn = sqlite3.connect(sqlite_db)

# انتقال داده‌ها به یک جدول به نام 'my_table'
df.to_sql('my_table', conn, if_exists='replace', index=False)

# بستن اتصال به پایگاه داده
conn.close()

print("تبدیل اکسل به SQLite با موفقیت انجام شد!")