from flask import Flask, jsonify, request, render_template
from dotenv import load_dotenv
import csv
import io
import sqlite3
import requests
import os

load_dotenv()

def init_db():
    conn = sqlite3.connect('scores.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_name TEXT NOT NULL,
            student_id TEXT,
            name TEXT NOT NULL,
            course TEXT NOT NULL,
            score REAL NOT NULL,
            UNIQUE(dataset_name, student_id, course)
        )
    ''')
    conn.commit()
    conn.close()

app = Flask(__name__)
init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/datasets', methods=['GET'])
def get_datasets():
    conn = sqlite3.connect('scores.db')
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT dataset_name FROM scores ORDER BY dataset_name DESC")
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row[0] for row in rows])

@app.route('/api/scores', methods=['GET'])
def get_scores():
    student_id = request.args.get('student_id')
    name = request.args.get('name')
    course = request.args.get('course')
    dataset_name = request.args.get('dataset_name')

    conn = sqlite3.connect('scores.db')
    cursor = conn.cursor()

    sql = "SELECT * FROM scores WHERE 1=1"
    params = []
    if dataset_name:
        sql += " AND dataset_name = ?"
        params.append(dataset_name)
    if student_id:
        sql += " AND student_id = ?"
        params.append(student_id)
    if name:
        sql += " AND name = ?"
        params.append(name)
    if course:
        sql += " AND course = ?"
        params.append(course)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        result.append({
            "id": row[0],
            "dataset_name": row[1],
            "student_id": row[2],
            "name": row[3],
            "course": row[4],
            "score": row[5]
        })
    return jsonify(result)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    course = request.args.get('course')
    dataset_name = request.args.get('dataset_name')

    conn = sqlite3.connect('scores.db')
    cursor = conn.cursor()

    where_clause = " WHERE 1=1"
    params = []
    if course:
        where_clause += " AND course = ?"
        params.append(course)
    if dataset_name:
        where_clause += " AND dataset_name = ?"
        params.append(dataset_name)

    cursor.execute(f"SELECT AVG(score), MAX(score), MIN(score), COUNT(*) FROM scores{where_clause}", params)
    row = cursor.fetchone()
    avg_score = round(row[0], 1) if row[0] else 0
    max_score = row[1] if row[1] else 0
    min_score = row[2] if row[2] else 0
    total_count = row[3]

    pass_where = " WHERE score >= 60"
    pass_params = []
    if course:
        pass_where += " AND course = ?"
        pass_params.append(course)
    if dataset_name:
        pass_where += " AND dataset_name = ?"
        pass_params.append(dataset_name)
    cursor.execute(f"SELECT COUNT(*) FROM scores{pass_where}", pass_params)
    pass_count = cursor.fetchone()[0]
    pass_rate = f"{(pass_count / total_count * 100):.1f}%" if total_count > 0 else "0%"

    dist_where = " WHERE 1=1"
    dist_params = []
    if course:
        dist_where += " AND course = ?"
        dist_params.append(course)
    if dataset_name:
        dist_where += " AND dataset_name = ?"
        dist_params.append(dataset_name)

    cursor.execute(f'''
        SELECT 
            SUM(CASE WHEN score < 60 THEN 1 ELSE 0 END) as fail,
            SUM(CASE WHEN score >= 60 AND score < 70 THEN 1 ELSE 0 END) as pass,
            SUM(CASE WHEN score >= 70 AND score < 80 THEN 1 ELSE 0 END) as good,
            SUM(CASE WHEN score >= 80 AND score < 90 THEN 1 ELSE 0 END) as great,
            SUM(CASE WHEN score >= 90 THEN 1 ELSE 0 END) as excellent
        FROM scores{dist_where}
    ''', dist_params)
    dist = cursor.fetchone()
    distribution = [dist[0] or 0, dist[1] or 0, dist[2] or 0, dist[3] or 0, dist[4] or 0]

    conn.close()

    current_label = course if course else "全部科目"
    return jsonify({
        "avg_score": avg_score,
        "max_score": max_score,
        "min_score": min_score,
        "total_count": total_count,
        "pass_rate": pass_rate,
        "distribution": distribution,
        "current_course": current_label
    })

@app.route('/api/course_stats', methods=['GET'])
def get_course_stats():
    dataset_name = request.args.get('dataset_name')
    conn = sqlite3.connect('scores.db')
    cursor = conn.cursor()

    if dataset_name:
        cursor.execute('''
            SELECT course, AVG(score) 
            FROM scores 
            WHERE dataset_name = ?
            GROUP BY course 
            ORDER BY AVG(score) DESC
        ''', (dataset_name,))
    else:
        cursor.execute('''
            SELECT course, AVG(score) 
            FROM scores 
            GROUP BY course 
            ORDER BY AVG(score) DESC
        ''')
    rows = cursor.fetchall()
    conn.close()

    courses = []
    averages = []
    for row in rows:
        courses.append(row[0])
        averages.append(round(row[1], 1))

    return jsonify({
        "courses": courses,
        "averages": averages
    })

@app.route('/api/import', methods=['POST'])
def import_scores():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "没有检测到文件"})

    file = request.files['file']
    dataset_name = request.form.get('dataset_name', '').strip() or '默认数据集'

    if file.filename == '':
        return jsonify({"status": "error", "message": "文件名为空"})

    try:
        stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
        csv_reader = csv.DictReader(stream)

        new_data = []
        error_logs = []
        for index, row in enumerate(csv_reader, start=2):
            student_id = row.get("学号") or row.get("student_id") or ""
            name = row.get("姓名") or row.get("name")
            course = row.get("科目") or row.get("course")
            score_str = row.get("分数") or row.get("score")

            if not name:
                error_logs.append(f"第{index}行缺失姓名")
                continue
            if not course:
                error_logs.append(f"第{index}行缺失科目")
                continue
            if not score_str:
                error_logs.append(f"第{index}行缺失分数")
                continue

            try:
                score = float(score_str)
            except ValueError:
                error_logs.append(f"第{index}行分数不是数字({score_str})")
                continue

            if score < 0 or score > 100:
                error_logs.append(f"第{index}行分数超范围({score})")
                continue

            new_data.append({
                "student_id": student_id,
                "name": name,
                "course": course,
                "score": score
            })

        if not new_data:
            return jsonify({"status": "error", "message": f"导入失败，没有一条合法数据。错误详情：{'; '.join(error_logs[:3])}..."})

        conn = sqlite3.connect('scores.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scores WHERE dataset_name = ?", (dataset_name,))

        for item in new_data:
            cursor.execute('''
                INSERT INTO scores (dataset_name, student_id, name, course, score) 
                VALUES (?, ?, ?, ?, ?)
            ''', (dataset_name, item["student_id"], item["name"], item["course"], item["score"]))
        conn.commit()
        conn.close()

        if error_logs:
            return jsonify({
                "status": "warning",
                "message": f"数据集【{dataset_name}】导入 {len(new_data)} 条，拦截 {len(error_logs)} 条错误。"
            })
        else:
            return jsonify({"status": "success", "message": f"数据集【{dataset_name}】成功导入 {len(new_data)} 条数据！"})

    except Exception as e:
        return jsonify({"status": "error", "message": f"文件解析失败：{str(e)}"})

@app.route('/api/ai_summary', methods=['GET'])
def ai_summary():
    course = request.args.get('course')
    dataset_name = request.args.get('dataset_name')
    personality = request.args.get('personality', '可爱俏皮型')

    conn = sqlite3.connect('scores.db')
    cursor = conn.cursor()
    where = "WHERE 1=1"
    params = []
    if course:
        where += " AND course = ?"
        params.append(course)
    if dataset_name:
        where += " AND dataset_name = ?"
        params.append(dataset_name)

    cursor.execute(f"SELECT AVG(score), MAX(score), MIN(score), COUNT(*) FROM scores {where}", params)
    avg, max_s, min_s, count = cursor.fetchone()
    conn.close()

    if count == 0:
        return jsonify({"summary": "暂无数据，无法分析", "mood": "confused"})

    mood = "normal"
    if avg is not None:
        if avg < 60:
            mood = "worried"
        elif avg >= 80:
            mood = "happy"

    personality_prompt = ""
    if personality == '可爱俏皮型':
        personality_prompt = "请用可爱、俏皮、充满活力的语气，"
    elif personality == '傲娇型':
        personality_prompt = "请用傲娇、口是心非、有点别扭的语气，"
    elif personality == '调皮型':
        personality_prompt = "请用略带嘲弄但其实是关心的语气，"
    elif personality == '社恐型':
        personality_prompt = "请用内向、害羞、轻声细语的语气，"

    prompt = f"你是一个教学助手。当前{'科目：'+course if course else '全部科目'}的成绩如下：总人数{count}，平均分{avg:.1f}，最高分{max_s}，最低分{min_s}。{personality_prompt}请用一句话给出教学建议（不超过50字）。"

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return jsonify({"summary": "未配置 DEEPSEEK_API_KEY，请检查 .env 文件", "mood": "confused"})

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        response = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data, timeout=10)
        result = response.json()
        ai_text = result['choices'][0]['message']['content']
        return jsonify({"summary": ai_text, "mood": mood})
    except Exception as e:
        return jsonify({"summary": f"AI 分析失败：{str(e)}", "mood": "worried"})

@app.route('/api/ai_deep_analysis', methods=['GET'])
def ai_deep_analysis():
    course = request.args.get('course')
    dataset_name = request.args.get('dataset_name')
    personality = request.args.get('personality', '可爱俏皮型')

    conn = sqlite3.connect('scores.db')
    cursor = conn.cursor()
    where = "WHERE 1=1"
    params = []
    if course:
        where += " AND course = ?"
        params.append(course)
    if dataset_name:
        where += " AND dataset_name = ?"
        params.append(dataset_name)

    cursor.execute(f"SELECT COUNT(*), AVG(score), MAX(score), MIN(score) FROM scores {where}", params)
    count, avg, max_s, min_s = cursor.fetchone()

    if count == 0:
        return jsonify({"summary": "暂无数据，无法进行深入分析", "mood": "confused"})

    cursor.execute(f'''
        SELECT 
            SUM(CASE WHEN score >= 90 THEN 1 ELSE 0 END),
            SUM(CASE WHEN score >= 80 AND score < 90 THEN 1 ELSE 0 END),
            SUM(CASE WHEN score >= 60 AND score < 80 THEN 1 ELSE 0 END),
            SUM(CASE WHEN score < 60 THEN 1 ELSE 0 END)
        FROM scores {where}
    ''', params)
    excellent, good, pass_, fail = cursor.fetchone()

    cursor.execute(f"SELECT name FROM scores {where} ORDER BY score DESC LIMIT 1", params)
    top_row = cursor.fetchone()
    top_name = top_row[0] if top_row else "无"

    cursor.execute(f"SELECT name FROM scores {where} ORDER BY score ASC LIMIT 1", params)
    bottom_row = cursor.fetchone()
    bottom_name = bottom_row[0] if bottom_row else "无"

    conn.close()

    personality_prompt = ""
    if personality == '可爱俏皮型':
        personality_prompt = "请用可爱、俏皮、充满活力的语气，"
    elif personality == '傲娇型':
        personality_prompt = "请用傲娇、口是心非、有点别扭的语气，"
    elif personality == '调皮型':
        personality_prompt = "请用略带嘲弄但其实是关心的语气，"
    elif personality == '社恐型':
        personality_prompt = "请用内向、害羞、轻声细语的语气，"

    prompt = f"""你是一个专业的教学分析助手。
当前{'科目：'+course if course else '全部科目'}的详细成绩数据如下：
总人数：{count}人，平均分：{avg:.1f}分，最高分：{max_s}（{top_name}同学），最低分：{min_s}（{bottom_name}同学）。
成绩分布：优秀（90+）{excellent}人，良好（80-90）{good}人，及格（60-80）{pass_}人，不及格（60以下）{fail}人。

{personality_prompt}请根据以上详细数据，写一段200字左右的成绩分析报告。内容需包含：
1. 整体成绩分布特点；
2. 可能存在的问题；
3. 给出至少2条切实可行的教学或学习建议。
要求语言生动具体，条理清晰。"""

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return jsonify({"summary": "未配置 DEEPSEEK_API_KEY", "mood": "confused"})

    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 500
        }
        response = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data, timeout=15)
        result = response.json()
        ai_text = result['choices'][0]['message']['content']

        mood = "normal"
        if avg < 60:
            mood = "worried"
        elif avg >= 80:
            mood = "happy"

        return jsonify({"summary": ai_text, "mood": mood})
    except Exception as e:
        return jsonify({"summary": f"深入分析失败：{str(e)}", "mood": "worried"})

if __name__ == '__main__':
    app.run(debug=True)