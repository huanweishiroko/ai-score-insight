import csv
import random

surnames = ['张', '王', '李', '赵', '刘', '陈', '杨', '黄', '周', '吴', '徐', '孙', '马', '朱', '胡']
names = ['伟', '芳', '娜', '敏', '静', '磊', '军', '洋', '勇', '艳', '杰', '娟', '涛', '明', '超']
courses = ['数学', '语文', '英语', '物理', '化学', '生物']

def generate_scores(distribution_type):
    """根据类型生成分数"""
    if distribution_type == '1':    # 偏好
        score = int(random.gauss(85, 8))
    elif distribution_type == '2':  # 偏差
        score = int(random.gauss(55, 10))
    elif distribution_type == '3':  # 中等（标准正态）
        score = int(random.gauss(75, 12))
    elif distribution_type == '4':  # 两极分化
        if random.random() > 0.5:
            score = int(random.gauss(92, 5))  # 高分群
        else:
            score = int(random.gauss(45, 10)) # 低分群
    else:
        score = int(random.gauss(75, 15))
    return max(0, min(100, score))

def create_data(choice):
    """生成数据集"""
    data = []
    # 生成 80 个学生，每人 2 门课，共 160 条正常数据
    for i in range(1, 81):
        student_id = f"2024{i:03d}"
        name = random.choice(surnames) + random.choice(names)
        selected_courses = random.sample(courses, 2)
        
        for course in selected_courses:
            score = generate_scores(choice)
            data.append([student_id, name, course, score])
            
    # 故意混入 6 条典型错误数据（放在最后）
    error_data = [
        ['', '张三', '数学', 85],
        ['2024999', '', '英语', 75],
        ['2024988', '李四', '物理', 150],
        ['2024977', '王五', '化学', -10],
        ['2024966', '赵六', '生物', '优秀'],
        ['2024955', '钱七', '', 88]
    ]
    data.extend(error_data)
    return data

def main():
    print("="*40)
    print("📊 学生成绩测试数据生成器")
    print("="*40)
    print("请选择要生成的数据分布类型：")
    print("  1. 偏好（高分多，适合测试 AI 开心/夸奖）")
    print("  2. 偏差（低分多，适合测试 AI 担忧/补差建议）")
    print("  3. 中等（正态分布，适合常规图表测试）")
    print("  4. 两极分化（高分和低分各占一半，测试图表断层与AI深度分析）")
    print("  5. 随机混合（默认，全方位测试）")
    
    choice = input("\n👉 请输入数字 (1-5): ").strip()
    
    if choice not in ['1', '2', '3', '4', '5']:
        print("⚠️ 输入无效，默认按【随机混合】生成。")
        choice = '5'
        
    data = create_data(choice)
    
    # 根据选择命名文件，方便区分
    filenames = {
        '1': 'mock_data_high.csv',
        '2': 'mock_data_low.csv',
        '3': 'mock_data_normal.csv',
        '4': 'mock_data_polarized.csv',
        '5': 'mock_data_random.csv'
    }
    filename = filenames[choice]
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['学号', '姓名', '科目', '分数'])
        writer.writerows(data)
        
    print(f"\n✅ 成功生成数据：{filename}")
    print(f"📊 共 {len(data)} 条（包含 6 条故意的错误数据，用于测试异常拦截）")
    print("💡 别忘了去网页端导入测试 AI 反应和图表变化！")

if __name__ == '__main__':
    main()