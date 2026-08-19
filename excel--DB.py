import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

# تنظیمات اتصالات
PERSONNEL_DB_URI = 'sqlite:///personnel.db'
TRIPS_DB_URI = 'sqlite:///trips.db'
EXCEL_FILE = 'daily_trips.xlsx'

# ایجاد موتورهای اتصال
personnel_engine = create_engine(PERSONNEL_DB_URI)
trips_engine = create_engine(TRIPS_DB_URI)

def read_excel_data():
    """خواندن داده‌های تریپ روزانه از اکسل"""
    df = pd.read_excel(
        EXCEL_FILE,
        usecols=['personnel_id', 'trip_date', 'trip_number', 'start_time'],
        parse_dates=['trip_date']
    )
    
    # تبدیل زمان به فرمت HH:MM
    df['start_time'] = pd.to_datetime(df['start_time']).dt.strftime('%H:%M')
    
    return df.dropna(subset=['personnel_id'])

def process_trips_data(df):
    """پردازش داده‌ها و تبدیل به فرمت مورد نظر"""
    grouped = df.groupby(['personnel_id', 'trip_date'])
    
    result = []
    for (operator_id, trip_date), group in grouped:
        trips = {f'trip{i}': None for i in range(1, 7)}
        
        for _, row in group.sort_values('trip_number').iterrows():
            if 1 <= row['trip_number'] <= 6:
                trips[f'trip{row["trip_number"]}'] = row['start_time']
        
        result.append({
            'operator_id': operator_id,
            'trip_date': trip_date.strftime('%Y-%m-%d'),
            **trips
        })
    
    return pd.DataFrame(result)

def save_daily_trips(df):
    """ذخیره تریپ‌های روزانه در دیتابیس"""
    # به‌روزرسانی رکوردهای موجود یا درج رکوردهای جدید
    for _, row in df.iterrows():
        # بررسی وجود رکورد
        exists = pd.read_sql(
            f"SELECT 1 FROM operator_daily_trips WHERE operator_id = '{row['operator_id']}' AND trip_date = DATE('{row['trip_date']}')",
            trips_engine
        )
        
        if not exists.empty:
            # به‌روزرسانی رکورد موجود
            set_clause = ', '.join([f"{col} = '{row[col]}'" for col in row.index if col.startswith('trip') and row[col] is not None])
            update_query = f"""
            UPDATE operator_daily_trips
            SET {set_clause}
            WHERE operator_id = '{row['operator_id']}' AND trip_date = DATE('{row['trip_date']}')
            """
            trips_engine.execute(update_query)
        else:
            # درج رکورد جدید
            row.to_frame().T.to_sql(
                name='operator_daily_trips',
                con=trips_engine,
                if_exists='append',
                index=False
            )

def get_operator_daily_trips(operator_id, date):
    """دریافت تریپ‌های یک روز خاص برای راهبر"""
    query = f"""
    SELECT trip1, trip2, trip3, trip4, trip5, trip6
    FROM operator_daily_trips
    WHERE operator_id = '{operator_id}' AND trip_date = DATE('{date}')
    """
    return pd.read_sql(query, trips_engine)

if __name__ == "__main__":
    try:
        # 1. خواندن داده‌ها از اکسل
        raw_data = read_excel_data()
        
        # 2. پردازش و تبدیل ساختار
        processed_data = process_trips_data(raw_data)
        
        # 3. ذخیره در دیتابیس
        if not processed_data.empty:
            save_daily_trips(processed_data)
            print(f"تعداد رکوردهای پردازش شده: {len(processed_data)}")
            
            # 4. نمونه گزارش
            sample_operator = processed_data.iloc[0]['operator_id']
            today = datetime.today().strftime('%Y-%m-%d')
            trips = get_operator_daily_trips(sample_operator, today)
            print(f"\nتریپ‌های امروز  {sample_operator}:")
            print(trips.to_string(index=False))
        else:
            print("هیچ داده جدیدی برای پردازش یافت نشد")
            
    except Exception as e:
        print(f"خطا: {str(e)}")
    finally:
        personnel_engine.dispose()
        trips_engine.dispose()