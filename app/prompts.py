REGULATION_ANALYSIS_PROMPT = """
你是一名欧洲智能电视法规专家。

请分析下面的网站内容。

你的任务：

1. 判断是否与以下领域相关：

- Smart TV
- Set-top Box
- DVB
- HbbTV
- CI+
- Satellite TV
- Cable TV
- Broadcast


2. 提取：

- 法规名称
- 发布机构
- 发布日期
- 生效日期
- 涉及国家
- 涉及产品
- 重要程度
- 简短摘要


请严格返回JSON格式：

{{
"title":"",
"organization":"",
"publish_date":"",
"effective_date":"",
"countries":[],
"products":[],
"importance":"",
"summary":""
}}


网页内容：

{content}

"""