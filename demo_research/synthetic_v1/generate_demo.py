#!/usr/bin/env python3
"""ClinPath 2026 WP-D: wholly synthetic, reproducible teaching-research DEMO.
Never imports/writes production ClinPath DB. All effect sizes are assumed examples.
"""
from __future__ import annotations
import csv, json, random, math, hashlib
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict
import numpy as np
from scipy import stats
import statsmodels.api as sm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; FIG=ROOT/'figures'
DATA.mkdir(parents=True,exist_ok=True);FIG.mkdir(parents=True,exist_ok=True)
SEED=20261018
rng=np.random.default_rng(SEED)
py_rng=random.Random(SEED)
N=60
DIMS=[('medical_knowledge','医学知识运用',.10),('key_information','关键信息提取',.20),('differential_diagnosis','鉴别诊断与论证',.25),('evidence_integration','临床证据整合',.15),('clinical_decision','检查与临床决策',.20),('evidence_based_medicine','循证依据与安全意识',.10)]
LABEL='SYNTHETIC_DEMO_NOT_REAL_STUDENTS'
CASES=[('CASE-01','SLE','系统性红斑狼疮'),('CASE-02','RA','类风湿关节炎'),('CASE-03','AAV','ANCA相关性血管炎')]
STEPS=[('S1','关键信息提取'),('S2','初步诊断与问题表征'),('S3','鉴别诊断与论证'),('S4','辅助检查决策'),('S5','治疗决策与安全意识')]
CASE_BANK={
 'SLE':{
 'vague':['患者症状较多，考虑免疫性疾病。','有多系统问题，需要继续观察。','先查相关指标，再决定是什么病。','这些表现可能和免疫病有关。','可以考虑免疫治疗，需要进一步检查。'],
 'solid':['存在皮疹、关节痛、蛋白尿等多系统线索，应识别器官受累程度。','综合临床表现与自身抗体，考虑SLE并评估活动度和肾脏受累。','需与感染、其他结缔组织病及药物相关表现鉴别，逐项寻找支持和反证。','建议完善血常规、尿沉渣、尿蛋白定量、肾功能、补体和自身抗体，并判断检查时机。','治疗取决于器官受累程度，注意肾脏评估、感染筛查与药物监测。'],
 'advanced':['从光敏、口腔溃疡、关节炎和尿检异常提取跨器官证据，并优先评估肾脏及血液系统危险信号。','形成SLE工作诊断，同时区分分类标准与临床诊断、活动与损伤，并明确尚不确定的信息。','按感染、药物诱发狼疮和其他结缔组织病列出证据支持与反证；避免由单个抗体直接下结论。','分层安排尿蛋白/肌酐比、尿沉渣、肾功能、补体、抗dsDNA与器官评估，说明每项检查如何改变决策。','依据器官受累程度、患者风险和指南选择初步策略，讨论糖皮质激素负担、感染风险与随访指标。'],
 'followup':['还有哪些提示狼疮肾炎的客观证据？','哪些发现支持SLE，哪些发现尚不满足判断？','感染如何作为另一种解释被排除或证实？','如果尿蛋白显著升高，你的下一项检查是什么？','如何把脏器风险和治疗不良反应纳入选择？']},
 'RA':{
 'vague':['患者关节疼痛，可能是关节炎。','考虑风湿病，需要检验。','可能为RA，也可能是其他疾病。','检查类风湿指标。','考虑用药缓解关节痛。'],
 'solid':['关注对称性小关节肿痛、晨僵、持续时间及滑膜炎体征。','若持续滑膜炎并符合典型分布，需要综合考虑RA可能性。','鉴别骨关节炎、银屑病关节炎、感染性关节炎及晶体性关节炎。','完善RF、抗CCP、炎症指标及必要影像，并结合临床表现解读。','根据疾病活动度制订规范治疗和监测计划，注意禁忌证。'],
 'advanced':['系统提取持续性滑膜炎、受累关节计数、晨僵、功能受限与关节外表现，并识别急性单关节炎危险情况。','形成炎性多关节炎的问题表征，结合病程、分布和客观体征提出RA工作诊断。','按感染、结晶性、银屑病、系统性结缔组织病逐项匹配反证，避免仅凭RF阳性定论。','选择RF、抗CCP、ESR/CRP与关节影像，解释阴性抗体和早期疾病中检查局限性。','围绕早期达标治疗、个体风险和安全监测给出初步策略，并讨论随访中的疗效评估。'],
 'followup':['如何区分炎性与机械性关节痛？','仅RF阳性足够诊断RA吗？','哪一种鉴别诊断不能因抗体阳性而忽略？','哪些影像或化验结果会改变诊断把握？','如何设置治疗目标与安全监测？']},
 'AAV':{
 'vague':['可能存在血管炎。','考虑自身免疫病。','需要排除其他疾病。','检测ANCA与尿常规。','根据情况进行治疗。'],
 'solid':['关注上气道、肺和肾脏受累线索及短期器官损伤风险。','结合多器官损害评估AAV可能，避免单凭ANCA定诊。','需鉴别感染、抗GBM病和其他系统性免疫病。','完善尿沉渣、肾功能、胸部影像、ANCA亚型及其他定向检查。','按器官威胁程度决定转诊与初始处理，兼顾感染排查。'],
 'advanced':['提取血尿/蛋白尿、肺部症状、鼻窦病史等肺-肾综合征危险信号，优先识别危及器官功能的进展。','将快速进展性肾损伤与系统性炎症整合为问题表征，并提出AAV工作诊断及严重程度分层。','并行考虑感染性心内膜炎、抗GBM病和其他免疫病，明确ANCA假阳性/阴性的解释边界。','优先检查尿沉渣、肌酐动态、胸部CT及MPO/PR3-ANCA，必要时讨论病理与专科评估。','针对器官威胁制定及时会诊、监测和治疗决策框架，权衡免疫抑制与感染风险。'],
 'followup':['出现血尿和气促，首先排查什么危险情况？','ANCA阳性与临床诊断有何关系？','如何同时排除感染和抗GBM病？','哪些检查需优先而不是等待全套抗体？','出现器官威胁时治疗时机如何决策？']}
}

def bound(x): return round(float(np.clip(x,0,100)),1)
def write_csv(name,rows):
 if not rows:return
 with (DATA/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

participants=[]; assess=[]; sessions=[]; steps=[]
assigned=['CBL']*30+['CLINPATH']*30
py_rng.shuffle(assigned)
delta_diff=[6,18] # target scenario, NOT inferred from actual students
all_cases=['SLE','RA','AAV']
for i in range(N):
 sid=f'SYN-{i+1:03d}'; group=assigned[i]; cohort='教学批次A' if i<30 else '教学批次B'
 base=bound(rng.normal(62,8.2)); user_diffs=rng.normal(0,1.25,6)
 pre_dims=[bound(base+o+noise) for o,noise in zip([2,-3,-4,-1,-2,0],rng.normal(0,4.2,6))]
 target_gain= rng.normal(6,3.2) if group=='CBL' else rng.normal(18,5.2)
 target_gain+=max(0,64-base)*0.035
 post_dim_gains= ([.7,.8,1.0,.8,1.05,.75] if group=='CBL' else [.60,1.12,1.35,1.05,1.18,.85])
 post_dims=[bound(x+target_gain*k+rng.normal(0,3)) for x,k in zip(pre_dims,post_dim_gains)]
 participants.append({'study_id':sid,'data_origin':LABEL,'group':group,'cohort':cohort,'program':'临床医学本科见习（虚拟）','simulation_seed':SEED,'study_status':'SIMULATION_ONLY','ethics_or_consent':'NOT_APPLICABLE_SYNTHETIC'})
 for tp,vals in [('T0',pre_dims),('T1',post_dims)]:
  weighted=sum(s*w for s,(_,_,w) in zip(vals,DIMS))
  ra=bound(weighted+rng.normal(0,1.7));rb=bound(weighted+rng.normal(0,1.7))
  row={'study_id':sid,'data_origin':LABEL,'group':group,'cohort':cohort,'timepoint':tp,'assessment_case_id':'ASSESS-A' if tp=='T0' else 'ASSESS-B','assessment_type':'独立标准化病例（全合成）','rater_A_id':'SYN_RATER_A','rater_A_total':ra,'rater_B_id':'SYN_RATER_B','rater_B_total':rb,'independent_total':round((ra+rb)/2,2),'rater_origin':'SIMULATED_NOT_HUMAN','ai_scoring_used_for_primary_outcome':'NO'}
  row.update({name:val for (name,_,_),val in zip(DIMS,vals)})
  assess.append(row)
 for week,case in zip([1,3,5],all_cases):
  st=f'{sid}-W{week}'
  strength=float(np.clip((base-45)/45+.15*week+(0.12*week if group=='CLINPATH' else 0),.05,.97))
  training_score=bound(50+strength*35+rng.normal(0,4)) if group=='CLINPATH' else ''
  sessions.append({'session_id':st,'study_id':sid,'data_origin':LABEL,'group':group,'week':week,'case_code':case,'teaching_mode':'ClinPath AI辅助＋教师反馈' if group=='CLINPATH' else '常规CBL病例讨论','completed':'YES','training_score_internal':training_score,'evaluation_mode':'SIMULATED_AI' if group=='CLINPATH' else 'NO_AI','model_id':'SIMULATED_TEXT_LIBRARY' if group=='CLINPATH' else 'NONE','synthetic_teacher_intervention':'鉴别诊断强化与反证追问' if group=='CLINPATH' and strength<.7 else ('教师总结讲解' if group=='CBL' else '个体反馈复核'),'date_relative':'第'+str(week)+'周'})
  if group=='CLINPATH':
   for j,(step_id,step_label) in enumerate(STEPS):
    style= 'vague' if strength<.36 else ('solid' if strength<.72 else 'advanced')
    first=CASE_BANK[case][style][j]
    alternate=CASE_BANK[case]['advanced'][j]
    revision=alternate if style!='advanced' else first+' 同时补充必要的反证与随访评估。'
    if j in [0,2] and py_rng.random()<.34: first='结合已知资料，我的初步判断是：'+first
    steps.append({'session_id':st,'study_id':sid,'data_origin':LABEL,'group':group,'case_code':case,'step_id':step_id,'step_label':step_label,'initial_student_answer_synthetic':first,'ai_tutor_question_synthetic':CASE_BANK[case]['followup'][j],'revised_student_answer_synthetic':revision,'answer_text_generation':'MODEL_AUTHORED_TEMPLATE_PLUS_DETERMINISTIC_VARIATION','is_real_student':'NO','model_call_per_row':'NO'})
write_csv('participants_SYNTHETIC.csv',participants)
write_csv('assessments_SYNTHETIC.csv',assess)
write_csv('learning_sessions_SYNTHETIC.csv',sessions)
write_csv('reasoning_steps_SYNTHETIC.csv',steps)

by={r['study_id']:r for r in participants}
a={(r['study_id'],r['timepoint']):r for r in assess}
analysis=[]
for sid,person in by.items():
 pre=a[(sid,'T0')]['independent_total'];post=a[(sid,'T1')]['independent_total']
 analysis.append({'study_id':sid,'data_origin':LABEL,'group':person['group'],'pre_score':pre,'post_score':post,'gain_score':round(post-pre,2)})
write_csv('analysis_ready_SYNTHETIC.csv',analysis)
cbl=[r for r in analysis if r['group']=='CBL'];tr=[r for r in analysis if r['group']=='CLINPATH']
x=np.array([r['gain_score'] for r in cbl]);y=np.array([r['gain_score'] for r in tr]);stat,p_gain=stats.ttest_ind(y,x,equal_var=False)
se=math.sqrt(y.var(ddof=1)/len(y)+x.var(ddof=1)/len(x))
nu=((y.var(ddof=1)/len(y)+x.var(ddof=1)/len(x))**2)/((y.var(ddof=1)/len(y))**2/(len(y)-1)+(x.var(ddof=1)/len(x))**2/(len(x)-1))
delta=float(y.mean()-x.mean());ci=stats.t.interval(.95,nu,loc=delta,scale=se)
pre=np.array([r['pre_score'] for r in analysis]);post=np.array([r['post_score'] for r in analysis]);tg=np.array([1 if r['group']=='CLINPATH' else 0 for r in analysis])
X=sm.add_constant(np.column_stack([tg,pre]));res=sm.OLS(post,X).fit(cov_type='HC3')
anc_ci=res.conf_int()[1].tolist()
metrics={'data_origin':LABEL,'seed':SEED,'n_students':N,'n_CBL':len(cbl),'n_CLINPATH':len(tr),'n_assessments':len(assess),'n_learning_sessions':len(sessions),'n_synthetic_reasoning_steps':len(steps),'groups':{},'illustrative_statistics':{'gain_diff_clinpath_minus_cbl':round(delta,2),'welch_t_stat':round(float(stat),3),'welch_t_p':float(p_gain),'gain_diff_ci95':[round(float(z),2) for z in ci],'ancova_clinpath_effect_adjusting_T0':round(float(res.params[1]),2),'ancova_hc3_p':float(res.pvalues[1]),'ancova_ci95':[round(float(z),2) for z in anc_ci],'analysis_note':'ALL VALUES ARE SYNTHETIC. The improvement was deliberately assumed in the simulator. These p-values are not evidence of educational effectiveness.'},'scenario_assumptions':{'nominal_CBL_gain':6,'nominal_CLINPATH_gain':18,'measurement':'two computer-simulated raters, not real humans','scale':'0-100'} }
for group,rows in [('CBL',cbl),('CLINPATH',tr)]:
 metrics['groups'][group]={'n':len(rows),'pre_mean':round(float(np.mean([r['pre_score'] for r in rows])),2),'post_mean':round(float(np.mean([r['post_score'] for r in rows])),2),'gain_mean':round(float(np.mean([r['gain_score'] for r in rows])),2),'gain_sd':round(float(np.std([r['gain_score'] for r in rows],ddof=1)),2)}
(ROOT/'metrics_SYNTHETIC.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')

# Sample plot intentionally repeats caveat in title and lower strip.
plt.rcParams['font.sans-serif']=['Noto Sans CJK JP','DejaVu Sans']
plt.rcParams['axes.unicode_minus']=False
fig,ax=plt.subplots(figsize=(9,5.4));g=['CBL','ClinPath'];v=[[metrics['groups'][k]['pre_mean'],metrics['groups'][k]['post_mean']] for k in ['CBL','CLINPATH']]
for group,xy in zip(g,v):ax.plot([0,1],xy,'o-',lw=2,markersize=8,label=group)
ax.set_xticks([0,1],['T0 基线','T1 结课']);ax.set_ylabel('独立病例模拟评分（0–100）');ax.set_ylim(45,100)
ax.set_title('ClinPath 模拟教学情景：两组前后测\n仅用于演示｜所有学生及教师评分均为合成')
ax.grid(axis='y',alpha=.2);ax.legend()
fig.text(.5,.02,'合成数据・预设差异・不得作为真实教学效果或实际试点结果',ha='center',fontsize=11)
fig.tight_layout(rect=(0,.05,1,1));fig.savefig(FIG/'prepost_SYNTHETIC.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(figsize=(9,5.0));bp=ax.boxplot([x,y],tick_labels=['常规CBL','ClinPath'],patch_artist=True)
for patch in bp['boxes']:patch.set_alpha(.4)
ax.set_ylabel('T1−T0模拟提升分数');ax.set_title('演示性增量分布（n=30/组）｜预设ClinPath较大增益')
ax.grid(axis='y',alpha=.2);fig.text(.5,.02,'合成数据・统计学显著性来自模拟假设，不是实际效果证明',ha='center',fontsize=10)
fig.tight_layout(rect=(0,.05,1,1));fig.savefig(FIG/'gain_distribution_SYNTHETIC.png',dpi=170);plt.close(fig)

# Empty real review template; do not forge expert reviewer participation.
review=[]
for reviewer in ['REAL_EXPERT_1_TODO','REAL_EXPERT_2_TODO']:
 for code,_,disease in CASES+[('CASE-04','IIM','炎性肌病'),('ASSESS-A','PRE','独立前测病例'),('ASSESS-B','POST','独立后测病例')]:
  review.append({'reviewer_slot':reviewer,'reviewer_name':'','review_date':'','case_id':code,'case_topic':disease,'medical_accuracy_1to5':'','undergraduate_fit_1to5':'','difficulty_1to5':'','rubric_clarity_1to5':'','feedback':'','final_approval':'PENDING_REAL_REVIEW','review_origin':'REAL_HUMAN_REVIEW_NOT_YET_CONDUCTED'})
with (ROOT/'templates'/'expert_review_BLANK.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(review[0]));w.writeheader();w.writerows(review)

# Dictionary to support future real study data intake. Data provenance explicit.
fields=[
 ('participants','study_id','string','唯一匿名研究号；真实研究以现场分配编号替代，严禁用姓名','必填'),
 ('participants','data_origin','enum','SYNTHETIC_DEMO_NOT_REAL_STUDENTS 或 REAL_CONSENTED','必填'),
 ('participants','group','enum','CBL / CLINPATH','必填'),
 ('participants','cohort','string','见习轮转批次','必填'),
 ('participants','ethics_or_consent','string','真实研究记录同意/伦理状态；演示为NOT_APPLICABLE_SYNTHETIC','必填'),
 ('assessments','timepoint','enum','T0 / T1；真实研究时间由方案指定','必填'),
 ('assessments','assessment_case_id','string','独立前后测病例编号，训练库不复用','必填'),
 ('assessments','independent_total','number (0-100)','独立教师评分主结局；演示由虚拟评分者生成','必填'),
 ('assessments','rater_A_total','number (0-100)','评分者A总分；真实研究须真实评分记录','必填'),
 ('assessments','rater_B_total','number (0-100)','评分者B总分；真实研究须真实评分记录','必填'),
 ('assessments','rater_origin','enum','SIMULATED_NOT_HUMAN / REAL_BLINDED_RATER','必填'),
 ('assessments','medical_knowledge','number (0-100)','医学知识运用维度','必填'),
 ('assessments','key_information','number (0-100)','关键信息提取维度','必填'),
 ('assessments','differential_diagnosis','number (0-100)','鉴别诊断维度','必填'),
 ('assessments','evidence_integration','number (0-100)','临床证据整合维度','必填'),
 ('assessments','clinical_decision','number (0-100)','检查与临床决策维度','必填'),
 ('assessments','evidence_based_medicine','number (0-100)','循证依据与安全意识维度','必填'),
 ('sessions','session_id','string','训练记录唯一ID','必填'),
 ('sessions','training_score_internal','number/empty','平台内部形成性评分，不得替代独立主要结局','选填'),
 ('sessions','evaluation_mode','enum','SIMULATED_AI / REAL_AI / RULE_FALLBACK / NO_AI','必填'),
 ('sessions','model_id','string','真实调用模型版本，合成数据注明模拟生成策略','条件必填'),
 ('reasoning_steps','initial_student_answer_synthetic','text','模型风格模拟学生初次作答，非真实学生文字','演示必填'),
 ('reasoning_steps','ai_tutor_question_synthetic','text','模拟AI追问，非必然为实际API结果','演示必填'),
 ('reasoning_steps','revised_student_answer_synthetic','text','模拟学生修订作答','演示必填'),
 ('analysis','gain_score','formula/number','T1−T0；真实研究优先比较基线校正后组间差异','衍生字段'),
 ('expert_review','reviewer_name','string','须由实际参与教师填写，不能合成','真实审核必填'),
 ('expert_review','final_approval','enum','PENDING / APPROVED / REVISE；完成前不得声称已审核','真实审核必填'),
]
with (ROOT/'data_dictionary.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.writer(f);w.writerow(['entity','field','type','definition','requirement']);w.writerows(fields)
print(json.dumps(metrics,ensure_ascii=False,indent=2))
