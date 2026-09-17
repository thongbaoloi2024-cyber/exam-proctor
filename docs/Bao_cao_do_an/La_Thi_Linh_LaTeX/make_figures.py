import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, FancyArrowPatch, Polygon
import numpy as np
from pathlib import Path

out = Path('Images')
out.mkdir(exist_ok=True)

# 1 architecture
fig, ax = plt.subplots(figsize=(12,7))
ax.axis('off')
boxes = [
    (0.04,0.72,0.16,0.12,'Camera CCTV'),
    (0.25,0.72,0.18,0.12,'YOLOv8\nPerson + Phone'),
    (0.48,0.72,0.16,0.12,'ByteTrack\nMOT'),
    (0.69,0.72,0.23,0.12,'ROI + Identity\nAssociation'),
    (0.14,0.43,0.22,0.12,'Presence\nState Machine'),
    (0.43,0.43,0.22,0.12,'Phone Usage\nState Machine'),
    (0.72,0.43,0.22,0.12,'Work-time\nAggregator'),
    (0.22,0.14,0.22,0.12,'FastAPI +\nWebSocket'),
    (0.53,0.14,0.18,0.12,'PostgreSQL +\nEvidence Store'),
    (0.78,0.14,0.18,0.12,'Dashboard +\nReports')
]
for x,y,w,h,t in boxes:
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02',fill=False,linewidth=1.5))
    ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=11)
for a,b in [(0,1),(1,2),(2,3),(3,4),(3,5),(4,6),(5,6),(6,7),(7,8),(8,9)]:
    xa,ya,wa,ha,_=boxes[a]; xb,yb,wb,hb,_=boxes[b]
    p1=(xa+wa/2,ya) if yb<ya else (xa+wa,ya+ha/2)
    p2=(xb+wb/2,yb+hb) if yb<ya else (xb,yb+hb/2)
    ax.add_patch(FancyArrowPatch(p1,p2,arrowstyle='->',mutation_scale=14,linewidth=1.2))
ax.set_xlim(0,1); ax.set_ylim(0,1)
fig.tight_layout(); fig.savefig(out/'new_architecture.png',dpi=220,bbox_inches='tight'); plt.close(fig)

# 2 ROI scene
fig, ax = plt.subplots(figsize=(11,6.5))
ax.set_xlim(0,100); ax.set_ylim(0,60); ax.set_aspect('equal'); ax.axis('off')
ax.add_patch(Rectangle((2,2),96,56,fill=False,linewidth=2))
rois=[(8,8,24,20,'ROI NV001'),(38,8,24,20,'ROI NV002'),(68,8,24,20,'ROI NV003')]
for x,y,w,h,label in rois:
    ax.add_patch(Rectangle((x,y),w,h,fill=False,linestyle='--',linewidth=1.5))
    ax.text(x+2,y+h-3,label,fontsize=10)
# desks
for x in [10,40,70]:
    ax.add_patch(Rectangle((x,11),20,6,fill=False,linewidth=1.2))
# persons with boxes, anchor points
persons=[(15,18,10,26,'T17'),(45,18,10,26,'T21'),(75,18,10,26,'T09')]
for x,y,w,h,tid in persons:
    ax.add_patch(Rectangle((x,y),w,h,fill=False,linewidth=1.5))
    ax.text(x,y+h+1,tid,fontsize=9)
    ax.plot([x+w/2],[y],marker='o',markersize=5)
# phone near second person
ax.add_patch(Rectangle((54,29),3,5,fill=False,linewidth=1.3))
ax.text(58,31,'cell phone',fontsize=9,va='center')
ax.text(50,55,'Khung hình camera cố định và các vùng làm việc đa giác (mô phỏng)',ha='center',fontsize=12)
fig.tight_layout(); fig.savefig(out/'roi_scene.png',dpi=220,bbox_inches='tight'); plt.close(fig)

# State machine helper

def state_machine(path, title, states, edges):
    fig, ax = plt.subplots(figsize=(11,5))
    ax.axis('off'); ax.set_xlim(0,1); ax.set_ylim(0,1)
    xs=np.linspace(0.12,0.88,len(states)); y=0.5
    pts={}
    for x,s in zip(xs,states):
        ax.add_patch(FancyBboxPatch((x-0.09,y-0.07),0.18,0.14,boxstyle='round,pad=0.02',fill=False,linewidth=1.5))
        ax.text(x,y,s,ha='center',va='center',fontsize=10)
        pts[s]=(x,y)
    for s1,s2,label,rad in edges:
        x1,y1=pts[s1]; x2,y2=pts[s2]
        ax.add_patch(FancyArrowPatch((x1+0.09*np.sign(x2-x1),y1),(x2-0.09*np.sign(x2-x1),y2),arrowstyle='->',mutation_scale=13,connectionstyle=f'arc3,rad={rad}',linewidth=1.1))
        ax.text((x1+x2)/2, y1+0.10+(0.10 if rad<0 else 0), label, ha='center', fontsize=8)
    ax.text(0.5,0.86,title,ha='center',fontsize=12)
    fig.tight_layout(); fig.savefig(out/path,dpi=220,bbox_inches='tight'); plt.close(fig)

state_machine('presence_state.png','Máy trạng thái hiện diện (mô phỏng)',
              ['ABSENT','CANDIDATE','PRESENT','GRACE'],
              [('ABSENT','CANDIDATE','phát hiện trong ROI',0),('CANDIDATE','PRESENT','duy trì >= T_enter',0),('PRESENT','GRACE','mất detection',0),('GRACE','PRESENT','phát hiện lại',-0.35),('GRACE','ABSENT','mất > T_gap',0.25)])
state_machine('phone_state.png','Máy trạng thái sử dụng điện thoại (mô phỏng)',
              ['NO_PHONE','CANDIDATE','USING','GRACE'],
              [('NO_PHONE','CANDIDATE','phone gần person',0),('CANDIDATE','USING','duy trì >= T_phone',0),('USING','GRACE','mất phone',0),('GRACE','USING','thấy lại',-0.35),('GRACE','NO_PHONE','mất > T_exit',0.25)])

# Timeline simulation
fig, ax = plt.subplots(figsize=(11,4.5))
ax.set_xlim(8,17.5); ax.set_ylim(0,4); ax.set_yticks([3,2,1]); ax.set_yticklabels(['Hiện diện','Dùng điện thoại','Giờ hiệu lực'])
ax.set_xlabel('Giờ trong ngày')
# intervals
presence=[(8.05,12.0),(13.05,17.25)]
phone=[(9.2,9.32),(10.75,10.93),(14.1,14.42),(16.05,16.18)]
for a,b in presence: ax.broken_barh([(a,b-a)],(2.7,0.6),facecolors='none',edgecolors='black',linewidth=3)
for a,b in phone: ax.broken_barh([(a,b-a)],(1.7,0.6),facecolors='none',edgecolors='black',hatch='///',linewidth=1.2)
# effective excludes excess after 15min total approximate - show same intervals minus last chunk
for a,b in [(8.05,12.0),(13.05,16.05),(16.18,17.25)]: ax.broken_barh([(a,b-a)],(0.7,0.6),facecolors='none',edgecolors='black',linewidth=2)
ax.grid(axis='x',alpha=.25)
fig.tight_layout(); fig.savefig(out/'sim_timeline.png',dpi=220,bbox_inches='tight'); plt.close(fig)

# Metrics comparison simulated
methods=['Frame+ROI','+ByteTrack','Đề xuất']
pres_f1=[0.86,0.92,0.95]
mae=[192,96,54]
fig, ax = plt.subplots(figsize=(9,5))
x=np.arange(len(methods)); bars=ax.bar(x,pres_f1,fill=False,edgecolor='black',hatch=['','//','xx'])
ax.set_ylim(0.75,1.0); ax.set_ylabel('Presence F1'); ax.set_xticks(x); ax.set_xticklabels(methods)
for b,v in zip(bars,pres_f1): ax.text(b.get_x()+b.get_width()/2,v+0.004,f'{v:.2f}',ha='center',fontsize=9)
ax.grid(axis='y',alpha=.25); fig.tight_layout(); fig.savefig(out/'sim_presence_f1.png',dpi=220,bbox_inches='tight'); plt.close(fig)
fig, ax = plt.subplots(figsize=(9,5))
bars=ax.bar(x,mae,fill=False,edgecolor='black',hatch=['','//','xx'])
ax.set_ylabel('MAE thời gian (giây/ca)'); ax.set_xticks(x); ax.set_xticklabels(methods)
for b,v in zip(bars,mae): ax.text(b.get_x()+b.get_width()/2,v+5,str(v),ha='center',fontsize=9)
ax.grid(axis='y',alpha=.25); fig.tight_layout(); fig.savefig(out/'sim_time_mae.png',dpi=220,bbox_inches='tight'); plt.close(fig)

# phone errors
scenarios=['1 người','3 người','Che khuất','Điện thoại trên bàn','Gần biên ROI']
precision=[0.96,0.92,0.86,0.89,0.88]
recall=[0.94,0.90,0.82,0.84,0.85]
fig, ax=plt.subplots(figsize=(10,5))
x=np.arange(len(scenarios)); w=.35
ax.bar(x-w/2,precision,w,fill=False,edgecolor='black',hatch='//',label='Precision')
ax.bar(x+w/2,recall,w,fill=False,edgecolor='black',hatch='xx',label='Recall')
ax.set_ylim(.7,1); ax.set_xticks(x); ax.set_xticklabels(scenarios,rotation=15,ha='right'); ax.set_ylabel('Giá trị'); ax.legend(); ax.grid(axis='y',alpha=.25)
fig.tight_layout(); fig.savefig(out/'sim_phone_metrics.png',dpi=220,bbox_inches='tight'); plt.close(fig)

# latency simulation
components=['YOLO','ByteTrack','ROI/assoc.','Face verify*','Backend']
lat=[31,3,2,18,6]
fig,ax=plt.subplots(figsize=(9,5)); bars=ax.barh(components,lat,fill=False,edgecolor='black',hatch=['','//','xx','..','\\\\'])
ax.set_xlabel('Thời gian trung bình (ms)'); ax.grid(axis='x',alpha=.25)
for b,v in zip(bars,lat): ax.text(v+0.5,b.get_y()+b.get_height()/2,f'{v} ms',va='center',fontsize=9)
ax.text(0,-0.85,'* Face verification không chạy ở mọi frame.',fontsize=9)
fig.tight_layout(); fig.savefig(out/'sim_latency.png',dpi=220,bbox_inches='tight'); plt.close(fig)

print('generated')
