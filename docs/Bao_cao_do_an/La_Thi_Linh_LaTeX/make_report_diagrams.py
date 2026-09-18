"""Reproducible diagrams of the proposed architecture; no measured results."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Polygon
OUT=Path(__file__).resolve().parent/'Images'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11})
INK='#20394d'; BLUE='#e3eff7'; GREEN='#e3f2eb'; ORANGE='#fcf0db'; GREY='#f0f3f5'
def canvas(height=8):
    fig,ax=plt.subplots(figsize=(12,height));ax.set(xlim=(0,12),ylim=(0,height));ax.axis('off');return fig,ax
def box(ax,x,y,w,h,label,color=BLUE,size=11):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.04,rounding_size=0.12',facecolor=color,edgecolor=INK,lw=1.3,zorder=3))
    ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=size,color=INK,zorder=4)
def arrow(ax,points,label=None,xy=None):
    for a,b in zip(points[:-2],points[1:-1]): ax.plot([a[0],b[0]],[a[1],b[1]],color=INK,lw=1.25,zorder=1)
    ax.add_patch(FancyArrowPatch(points[-2],points[-1],arrowstyle='-|>',mutation_scale=13,lw=1.25,color=INK,zorder=2))
    if label: ax.text(*xy,label,ha='center',va='center',fontsize=9,color=INK,bbox=dict(facecolor='white',edgecolor='none',pad=2),zorder=5)
def save(fig,name):
    for ext in ['png','svg']: fig.savefig(OUT/f'{name}.{ext}',dpi=220,bbox_inches='tight',pad_inches=.12)
    plt.close(fig)

fig,ax=canvas(9)
ax.text(.25,8.7,'THIẾT BỊ BIÊN: thu nhận, nhận thức và tạo sự kiện',color=INK,weight='bold',fontsize=13)
box(ax,.25,7.35,2.3,.8,'Camera CCTV\nKhung hình + thời điểm')
box(ax,3.15,7.35,2.3,.8,'YOLOv8\nNgười + điện thoại')
box(ax,6.05,7.35,2.2,.8,'ByteTrack\nChỉ theo dõi người')
box(ax,8.95,7.35,2.8,.8,'ROI + danh tính\nFaceNet theo sự kiện')
arrow(ax,[(2.55,7.75),(3.15,7.75)])
arrow(ax,[(5.45,7.75),(6.05,7.75)],'Người',(5.75,8.3))
arrow(ax,[(8.25,7.75),(8.95,7.75)])
box(ax,3.15,5.15,3.1,.85,'Liên kết người - điện thoại\nGiữ UNKNOWN khi mơ hồ',GREEN)
box(ax,8.95,5.15,2.8,.85,'FSM hiện diện\nGhi khoảng mất quan sát',GREEN)
arrow(ax,[(4.3,7.35),(4.3,6)],'Điện thoại',(4.85,6.6))
arrow(ax,[(10.35,7.35),(10.35,6)])
arrow(ax,[(9.5,7.35),(9.5,6.55),(6.7,6.55),(6.7,5.57),(6.25,5.57)],'Quỹ đạo + ngữ cảnh',(7.5,6.55))
box(ax,3.15,3.35,3.1,.85,'FSM điện thoại\nPhiên + mốc liên kết cuối',GREEN)
arrow(ax,[(4.7,5.15),(4.7,4.2)])
arrow(ax,[(8.95,5.55),(7.75,5.55),(7.75,3.77),(6.25,3.77)],'Điều kiện\nhiện diện',(7.75,4.65))
box(ax,8.95,3.35,2.8,.85,'Hàng đợi bền vững\nSự kiện + số thứ tự',GREEN)
arrow(ax,[(6.25,3.6),(8.95,3.6)],'Phiên điện thoại',(7.6,3.27))
arrow(ax,[(10.35,5.15),(10.35,4.2)],'Khoảng hiện diện',(10.35,4.65))
ax.plot([.25,11.75],[2.9,2.9],ls='--',color='#78909c',lw=1)
ax.text(.25,2.58,'MÁY CHỦ: lưu trữ, tổng hợp và cung cấp dữ liệu',color=INK,weight='bold',fontsize=13)
box(ax,8.95,1.25,2.8,.85,'FastAPI / WebSocket\nXác thực + xác nhận ACK',ORANGE)
box(ax,4.85,1.25,3.2,.85,'Kho sự kiện / PostgreSQL\nTổng hợp theo ca + chính sách',ORANGE)
box(ax,.25,1.25,3.3,.85,'API / WebSocket\nBảng điều khiển + báo cáo',ORANGE)
arrow(ax,[(10.35,3.35),(10.35,2.1)])
arrow(ax,[(8.95,1.68),(8.05,1.68)])
arrow(ax,[(4.85,1.68),(3.55,1.68)])
ax.text(6,.55,'Ảnh bằng chứng được lưu riêng theo quyền truy cập. Cấu hình và lịch làm việc do máy chủ quản lý.',ha='center',fontsize=10,color=INK)
save(fig,'new_architecture')

def state_diagram(phone=False):
    fig,ax=canvas(7.4)
    title='Máy trạng thái phiên điện thoại' if phone else 'Máy trạng thái hiện diện'
    ax.text(6,7.08,title,ha='center',fontsize=15,weight='bold',color=INK)
    states=['NO_PHONE','CANDIDATE','USING','GRACE'] if phone else ['ABSENT','CANDIDATE','PRESENT','GRACE']
    for (x,y),name,color in zip([(1,5.1),(8.3,5.1),(8.3,2.7),(1,2.7)],states,[GREY,BLUE,GREEN,ORANGE]): box(ax,x,y,2.7,.75,name,color,12)
    arrow(ax,[(3.7,5.65),(8.3,5.65)],'Liên kết hợp lệ, hiện diện PRESENT' if phone else 'Ứng viên hợp lệ trong ROI',(6,5.98))
    arrow(ax,[(8.3,5.3),(3.7,5.3)],'Mất điều kiện trước khi xác nhận',(6,4.94))
    arrow(ax,[(9.65,5.1),(9.65,3.45)],'Đủ thời lượng\nvà điều kiện vào',(10.85,4.3))
    arrow(ax,[(8.3,3.24),(3.7,3.24)],'Mất liên kết tin cậy' if phone else 'Không thấy ứng viên',(6,3.63))
    arrow(ax,[(3.7,2.9),(8.3,2.9)],'Thấy lại trước khi hết khoảng đệm',(6,2.5))
    arrow(ax,[(2.35,3.45),(2.35,5.1)],'Hết khoảng đệm\nĐóng tại mốc cuối',(1.13,4.3))
    if phone:
        box(ax,.6,.62,10.8,1.12,'Quy tắc ưu tiên: hiện diện ABSENT / SUSPENDED → đóng phiên và về NO_PHONE.\nHiện diện GRACE: không mở phiên mới, chỉ giữ phiên đang mở trong khoảng đệm.\nPhiên đóng không muộn hơn mốc kết thúc hiện diện.',GREY,10.5)
    else:
        box(ax,.6,.62,3.15,1.12,'SUSPENDED\nThiếu dữ liệu quan sát',GREY,11)
        ax.text(4.05,1.55,'Từ mọi trạng thái: mất quan sát được xác nhận → SUSPENDED.',fontsize=10,color=INK)
        ax.text(4.05,1.12,'Nguồn phục hồi: có ứng viên → CANDIDATE, chưa có → ABSENT.',fontsize=10,color=INK)
        ax.text(4.05,.7,'Đóng khoảng tại mốc tin cậy cuối, không nối qua khoảng mù.',fontsize=10,color=INK)
    ax.text(6,.13,'Khi xác nhận vào, truy hồi mốc bắt đầu về thời điểm xuất hiện ứng viên.',ha='center',fontsize=10,color=INK)
    save(fig,'phone_state' if phone else 'presence_state')
state_diagram();state_diagram(True)

fig,ax=canvas(6.7)
ax.text(6,6.3,'Liên kết quỹ đạo với ROI qua điểm giữa cạnh đáy hộp bao',ha='center',fontsize=14,weight='bold',color=INK)
for idx,(x,track) in enumerate([(0.6,'T17'),(4.3,'T21'),(8,'T09')],1):
    ax.add_patch(Polygon([(x,.9),(x+3.2,.9),(x+2.85,3.2),(x+.35,3.2)],facecolor=BLUE,edgecolor=INK,lw=1.4,ls='--'))
    ax.text(x+1.6,1.15,f'ROI {idx:02d} / NV{idx:03d}',ha='center',fontsize=10,color=INK)
    ax.add_patch(Rectangle((x+1,1.85),1.2,3.35,facecolor='none',edgecolor=INK,lw=1.6))
    ax.text(x+1.6,5.42,track,ha='center',color=INK,weight='bold')
    ax.plot(x+1.6,1.85,'o',color='#167c6b',ms=8)
ax.add_patch(Rectangle((6.5,3.85),.27,.5,facecolor=ORANGE,edgecolor='#9f5d2d',lw=1.2))
ax.annotate('Điện thoại\nứng viên của T21',xy=(6.64,4.1),xytext=(7.55,4.85),fontsize=10,ha='center',arrowprops=dict(arrowstyle='->',color=INK),color=INK)
ax.text(6,.38,'Chấm tròn: điểm neo. Nét đứt: ROI. Hộp đứng: quỹ đạo. Sơ đồ hình học, không phải ảnh CCTV.',ha='center',fontsize=10,color=INK)
save(fig,'roi_scene')
print('Generated 4 diagrams in PNG and SVG.')
