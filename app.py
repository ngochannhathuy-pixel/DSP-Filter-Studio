import io, json, time
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import soundfile as sf
from scipy import signal
import dsp_core as d

st.set_page_config(page_title='DSP Filter Studio',page_icon='🎛️',layout='wide')

def chart(x, traces, xlabel='', ylabel='', key=None, mode='lines'):
    fig=go.Figure()
    for label,y in traces: fig.add_scatter(x=x,y=y,name=label,mode=mode)
    fig.update_layout(template='plotly_dark',height=330,margin=dict(l=45,r=20,t=15,b=45),xaxis_title=xlabel,yaxis_title=ylabel,legend=dict(orientation='h'),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig,use_container_width=True,key=key)

def read_audio(upload):
    x,fs=sf.read(io.BytesIO(upload.getvalue()),always_2d=True)
    if len(x)>fs*120: raise ValueError('Bản này giới hạn 120 giây mỗi tệp.')
    return x,fs

def coeff_input(s): return [float(v) for v in s.replace(';',',').replace(' ',',').split(',') if v]

def make_graph(b,a,kind):
    # DOT diagram: signal flows, gains and state delays, including feedback.
    lines=['digraph G { rankdir=LR; graph [bgcolor="transparent"]; node [shape=box]; x [label="x[n]"]; y [label="y[n]"];']
    def edge(src,dst,label=''): lines.append(f'{src} -> {dst} [label="{label}"];')
    def chain(prefix,start,k):
        nodes=[start]
        for i in range(1,k+1):
            node=f'{prefix}{i}'; lines.append(f'{node} [label="z^-1"];'); edge(nodes[-1],node); nodes.append(node)
        return nodes
    def add_sum(node): lines.append(f'{node} [shape=circle,label="+"];')
    if kind=='Direct Form I':
        add_sum('sum'); xx=chain('xd','x',len(b)-1); yy=chain('yd','y',len(a)-1)
        for i,v in enumerate(b):
            if v: edge(xx[i],'sum',f'{v:.5g}')
        for i,v in enumerate(a[1:],1):
            if v: edge(yy[i],'sum',f'{-v:.5g}')
        edge('sum','y')
    else:
        add_sum('w'); add_sum('out'); edge('x','w'); k=max(len(a),len(b))-1; ww=chain('wd','w',k)
        for i,v in enumerate(a[1:],1):
            if v: edge(ww[i],'w',f'{-v:.5g}')
        for i,v in enumerate(b):
            if v: edge(ww[i],'out',f'{v:.5g}')
        edge('out','y')
    return '\n'.join(lines+['}'])

st.title('🎛️ DSP Filter Studio')
st.caption('CHƯƠNG 6  /  HÀM TRUYỀN VÀ HIỆN THỰC BỘ LỌC  •  HCMUT  •  WORKBENCH v1.0')
with st.sidebar:
    st.header('01 / Tín hiệu đầu vào')
    source=st.selectbox('Nguồn', ['Demo âm thanh tổng hợp','Demo cảm biến tổng hợp','Tệp âm thanh','Microphone (ghi rồi lọc)','Tệp CSV','Tín hiệu sin/cos'])
    x=ref=None; audio=True
    try:
        if source=='Tệp âm thanh':
            up=st.file_uploader('WAV / FLAC / OGG / MP3*',type=['wav','flac','ogg','mp3']); fs=16000
            if up: x,fs=read_audio(up)
        elif source=='Microphone (ghi rồi lọc)':
            up=st.audio_input('Ghi âm',sample_rate=16000); fs=16000
            if up: x,fs=read_audio(up)
        elif source=='Tệp CSV':
            audio=False; fs=st.number_input('Fs (Hz)',1,192000,200); up=st.file_uploader('CSV: một cột tín hiệu, lấy mẫu đều',type=['csv'])
            if up:
                df=pd.read_csv(up,header=0 if st.checkbox('Có hàng tiêu đề',True) else None); col=st.selectbox('Cột tín hiệu',list(df.columns)); x=pd.to_numeric(df[col],errors='raise').to_numpy()[:,None]
        elif source=='Demo cảm biến tổng hợp':
            audio=False; fs=200; x,ref=d.demo(fs,8,'sensor'); x=x[:,None]; ref=ref[:,None]
        elif source=='Tín hiệu sin/cos':
            fs=st.selectbox('Fs (Hz)',[1000,8000,16000,44100,48000],index=2); f=st.number_input('Tần số (Hz)',0.,float(fs/2),min(440.,fs/4)); amp=st.slider('Biên độ',0.,1.,.6); phase=st.slider('Pha (độ)',-180,180,0); typ=st.radio('Dạng',['cos','sin'],horizontal=True); n=np.arange(fs*2); x=(amp*(np.cos if typ=='cos' else np.sin)(2*np.pi*f*n/fs+np.deg2rad(phase)))[:,None]
        else:
            fs=16000; x,ref=d.demo(fs); x=x[:,None]; ref=ref[:,None]
        if x is not None and (not len(x) or not np.all(np.isfinite(x)) or len(x)>2_000_000 or x.shape[1]>8): raise ValueError('Tín hiệu rỗng, có NaN/Inf, quá 2 triệu mẫu/kênh hoặc quá 8 kênh.')
    except Exception as e:
        st.error(str(e)); st.stop()
    st.caption(f'Fs = {fs:,} Hz  •  Nyquist = {fs/2:g} Hz')
    st.header('02 / Thiết lập bộ lọc')
    mode=st.radio('Phương thức',['Thiết kế theo tần số','Nhập hệ số H(z)','Nhập cực-zero','Preset ứng dụng'],horizontal=False)
    sos=None
    try:
        if mode=='Thiết kế theo tần số':
            family=st.selectbox('Họ bộ lọc',['Butterworth','FIR Hamming','Chebyshev I','Chebyshev II','Elliptic']); types={'Thông thấp':'lowpass','Thông cao':'highpass','Thông dải':'bandpass','Chắn dải':'bandstop','Notch (IIR bậc 2)':'notch'}; typ=st.selectbox('Loại',list(types)); kind=types[typ]
            ny=fs/2; default=12. if not audio else 1200.
            if kind=='notch':
                f0=st.number_input('Tần số triệt (Hz)',min_value=.001,max_value=float(ny*.999),value=min(50.,ny*.5),format='%.3f'); q=st.number_input('Q',min_value=.1,max_value=1000.,value=30.); b,a=signal.iirnotch(f0,q,fs=fs)
            else:
                fir=family=='FIR Hamming'; order=st.slider('Bậc thiết kế',1,80 if fir else 6,20 if fir else 4)
                if kind in ('bandpass','bandstop'):
                    f1=st.number_input('f1 (Hz)',min_value=.001,max_value=float(ny*.999),value=min(300. if audio else 2.,ny*.2),format='%.3f'); f2=st.number_input('f2 (Hz)',min_value=.001,max_value=float(ny*.999),value=min(3400. if audio else 12.,ny*.8),format='%.3f'); cut=[f1,f2]
                else: cut=st.number_input('fc (Hz)',min_value=.001,max_value=float(ny*.999),value=min(default,ny*.5),format='%.3f')
                rp=st.number_input('Ripple (dB)',.1,20.,1.) if family in ('Chebyshev I','Elliptic') else 1.; rs=st.number_input('Stopband (dB)',10.,120.,40.) if family in ('Chebyshev II','Elliptic') else 40.
                b,a,sos=d.design(family,kind,order,cut,fs,rp,rs)
        elif mode=='Nhập hệ số H(z)':
            st.caption('Theo thứ tự z⁰, z⁻¹, z⁻², …')
            b=coeff_input(st.text_input('b – tử số','0, 1')); a=coeff_input(st.text_input('a – mẫu số','1, -0.5'))
            if max(len(b),len(a))>41: raise ValueError('Nhập tối đa 41 hệ số mỗi đa thức.')
        elif mode=='Preset ứng dụng':
            preset=st.selectbox('Bài toán',['Giọng nói 300–3400 Hz + notch 50 Hz','Triệt hum 50 Hz','Làm mượt cảm biến 12 Hz','Triệt hum 60 Hz'])
            if preset.startswith('Giọng'):
                if fs/2<=3400: raise ValueError('Preset giọng nói cần Fs > 6800 Hz.')
                bp=signal.butter(3,[300,3400],btype='bandpass',fs=fs,output='sos'); nb,na=signal.iirnotch(50,30,fs=fs); sos=np.vstack([d.sections(nb,na),bp]); b,a=signal.sos2tf(sos)
            elif preset.startswith('Làm'):
                sos=signal.butter(4,12,fs=fs,output='sos'); b,a=signal.sos2tf(sos)
            else:
                f0=50 if '50' in preset else 60; b,a=signal.iirnotch(f0,30,fs=fs)
        else:
            st.caption('Ví dụ: 0.7+0.2j, 0.7-0.2j. Dùng cặp liên hợp để hệ số thực.')
            def cvals(s): return np.array([complex(v.strip()) for v in s.split(',') if v.strip()])
            z=cvals(st.text_input('Zero','-1')); p=cvals(st.text_input('Pole','0.7')); gain=st.number_input('Gain',value=0.15)
            if len(z)>len(p) or len(p)>20: raise ValueError('Cần số zero ≤ số pole (hệ nhân quả), tối đa 20 pole. Có thể thêm pole tại 0.')
            b,a=signal.zpk2tf(z,p,gain); b=np.pad(b,(len(p)-len(z),0)); b=np.real_if_close(b); a=np.real_if_close(a)
            if np.iscomplexobj(b) or np.iscomplexobj(a): raise ValueError('Bộ lọc phải có hệ số thực.')
        b,a=d.normalize(b,a)
        z,p=d.poles_zeros(b,a)
        if sos is None and max(len(b),len(a))<=25: sos=d.sections(b,a)
        if mode in ('Thiết kế theo tần số','Preset ứng dụng') and sos is not None and len(a)>1:
            # The native SOS design is numerically more robust for IIR.
            stable_native=bool(np.all(np.abs(signal.sos2zpk(sos)[1])<1))
        else: stable_native=d.stable(b,a)
    except Exception as e:
        st.error(f'Không tạo được bộ lọc: {e}'); st.stop()
    st.caption('Quy ước a₀ = 1; hồi tiếp dùng −aₖ. Hệ nhân quả, trạng thái đầu bằng 0.')

M,L=len(b)-1,len(a)-1; K=max(M,L); radius=float(np.max(np.abs(p))) if len(p) else 0.
metrics=st.columns(4)
for c,label,value in zip(metrics,['Loại cấu trúc','Bậc hiện thực','Bán kính cực lớn nhất (b/a)','Ổn định hiện thực'],['FIR không hồi tiếp' if L==0 else 'Có hồi tiếp',K,f'{radius:.6f}','Ổn định' if stable_native else 'Không ổn định']): c.metric(label,value)
if not stable_native: st.warning('Cực trên/ngoài vòng đơn vị: chặn xử lý âm thanh và đáp ứng tần số vật lý. Kiểm tra triệt cực-zero nếu có.')
if stable_native != d.stable(b,a): st.warning('Phân tích b/a và SOS khác nhau do điều kiện số; ưu tiên SOS gốc, tránh hiện thực trực tiếp b/a.')
tabs=st.tabs(['01 · Hàm truyền','02 · Cực-zero','03 · Đáp ứng','04 · Sin/cos','05 · Hiện thực','06 · Xử lý thực tế','07 · Kiểm chứng'])
with tabs[0]:
    st.subheader('Hàm truyền H(z) và phương trình sai phân')
    st.latex(r'H(z)=\frac{Y(z)}{X(z)}=\frac{'+d.formula(b)+'}{'+d.formula(a)+'}')
    def terms(v,name,start=0):
        return ''.join(f'{t:+.6g}{name}[n'+(f'-{i}' if i else '')+']' for i,t in enumerate(v) if i>=start and t!=0).lstrip('+')
    st.code('y[n] = '+(terms(b,'x') or '0')+ ((' + '+terms(-a,'y',1)) if np.any(a[1:]) else ''))
    st.dataframe(pd.DataFrame({'k':np.arange(K+1),'b[k]':np.pad(b,(0,K-M)),'a[k]':np.pad(a,(0,K-L))}),hide_index=True)
    st.caption('Nếu có triệt cực-zero chính xác, đáp ứng xung tối giản có thể là FIR dù dạng đang hiện thực có hồi tiếp.')
    st.download_button('Xuất hệ số JSON',json.dumps({'fs':fs,'b':b.tolist(),'a':a.tolist(),'sos':sos.tolist() if sos is not None else None},indent=2),'filter.json','application/json')
with tabs[1]:
    st.subheader('Mặt phẳng z và miền hội tụ')
    theta=np.linspace(0,2*np.pi,361); fig=go.Figure(); fig.add_scatter(x=np.cos(theta),y=np.sin(theta),name='|z|=1',mode='lines',line=dict(dash='dash')); fig.add_scatter(x=z.real,y=z.imag,name='Zero',mode='markers',marker=dict(symbol='circle-open',size=11)); fig.add_scatter(x=p.real,y=p.imag,name='Pole',mode='markers',marker=dict(symbol='x',size=11)); fig.update_yaxes(scaleanchor='x',scaleratio=1); fig.update_layout(height=500,xaxis_title='Re(z)',yaxis_title='Im(z)',template='plotly_dark'); st.plotly_chart(fig,use_container_width=True)
    st.write(f'ROC cho hiện thực nhân quả (trước khi xét triệt cực-zero): |z| > {radius:.6g}.' if len(p) else 'Không có cực hữu hạn; hàm truyền hằng.')
    st.caption('Đồ thị có cả cực/zero ở gốc do bậc tử và mẫu khác nhau; với bậc cao, tìm nghiệm đa thức có thể mất chính xác.')
    st.dataframe(pd.DataFrame([{'Loại':label,'Re':v.real,'Im':v.imag,'|z|':abs(v)} for label,arr in [('Zero',z),('Pole',p)] for v in arr]),hide_index=True)
with tabs[2]:
    st.subheader('Đáp ứng xung và bước')
    N=st.slider('Số mẫu khảo sát',16,256,64); delta=np.r_[1.,np.zeros(N-1)]; filt=lambda xx: signal.sosfilt(sos,xx) if sos is not None else signal.lfilter(b,a,xx)
    chart(np.arange(N),[('h[n]',filt(delta)),('s[n]',filt(np.ones(N)))],'n','Biên độ','imp',mode='lines+markers')
    if stable_native:
        w,hz,H=d.response(b,a,fs,sos=sos); unit=st.radio('Đơn vị tần số',['Hz','ω/π'],horizontal=True); axis=hz if unit=='Hz' else w/np.pi; xlabel='f (Hz)' if unit=='Hz' else 'ω/π'
        st.write('**Phân loại tự động (heuristic):** '+d.classify(b,a,sos))
        chart(axis,[('|H| (dB)',d.db(H))],xlabel,'dB','mag'); chart(axis,[('arg H',np.where(np.abs(H)>1e-10,np.angle(H),np.nan))],xlabel,'rad','phase')
        st.caption('Pha chính trong (−π, π]; bỏ điểm có biên độ gần 0. Phân loại theo hình dạng phổ, không phải bộ kiểm định thông số thiết kế.')
        if sos is not None: gd_w=np.linspace(0,np.pi,512); _,hh=signal.sosfreqz(sos,worN=gd_w); gd=-np.gradient(np.unwrap(np.angle(hh)),gd_w)
        else: gd_w,gd=signal.group_delay((b,a),w=512)
        chart(gd_w*fs/(2*np.pi),[('Group delay',gd)],'Hz','mẫu','gd')
with tabs[3]:
    st.subheader('Đáp ứng với tín hiệu sin/cos xác lập')
    ftest=st.number_input('Tần số thử (Hz)',0.,float(fs/2),min(440.,fs/4),key='sin_f'); A=st.number_input('A',value=1.); phi=st.number_input('Pha φ (độ)',value=0.); waveform=st.radio('Dạng vào',['cos','sin'],horizontal=True,key='test_type'); omega=2*np.pi*ftest/fs
    if stable_native:
        _,hh=signal.sosfreqz(sos,worN=[omega]) if sos is not None else signal.freqz(b,a,worN=[omega]); gain=abs(hh[0]); angle=np.angle(hh[0]) if gain>1e-10 else 0.; fn=np.cos if waveform=='cos' else np.sin; n=np.arange(256); xx=A*fn(omega*n+np.deg2rad(phi)); yy=A*gain*fn(omega*n+np.deg2rad(phi)+angle); actual=filt(xx)
        st.latex(r'y_{ss}[n]=A|H(e^{j\omega})|\,'+waveform+r'(\omega n+\phi+\arg H(e^{j\omega}))')
        st.write(f'|H| = {gain:.6g}; pha = {np.rad2deg(angle):.5g}° (không xác định nếu |H|≈0); ω = {omega:.5g} rad/mẫu')
        chart(n,[('x[n]',xx),('y xác lập lý thuyết',yy),('y trạng thái đầu 0',actual)],'n','Biên độ','sin')
        st.caption('Hai kết quả y có thể khác ở quá độ vì trạng thái đầu bằng 0.')
with tabs[4]:
    st.subheader('Sơ đồ hiện thực và bảng xử lý mẫu')
    form=st.radio('Cấu trúc',['Direct Form I','Direct Form II','Cascade SOS'],horizontal=True)
    adds=max(0,np.count_nonzero(b)+np.count_nonzero(a[1:])-1); mult=np.count_nonzero(b)+np.count_nonzero(a[1:]); counts=[['DF-I',M+L,int(adds),int(mult)],['DF-II',K,int(adds),int(mult)]]
    if sos is not None:
        # Each biquad is a conventional two-state implementation, even if first order.
        sos_add=sum(max(0,np.count_nonzero(r[:3])+np.count_nonzero(r[4:])-1) for r in sos); sos_mult=sum(np.count_nonzero(r[:3])+np.count_nonzero(r[4:]) for r in sos); counts.append(['SOS (2 trạng thái/section)',2*len(sos),int(sos_add),int(sos_mult)])
    st.dataframe(pd.DataFrame(counts,columns=['Dạng','Bộ trễ cấp phát','Cộng/trừ (ước lượng)','Nhân (kể cả ±1)']),hide_index=True); st.caption('Mô hình phép toán với tổng nhiều ngõ vào quy về bộ cộng hai ngõ vào; chưa tối ưu hệ số ±1.')
    if form=='Cascade SOS':
        if sos is not None:
            dot='digraph G { rankdir=LR; x; y; '+'; '.join(f's{i} [shape=box,label="SOS {i+1}\\nDF-II"]' for i in range(len(sos)))+'; x -> '+' -> '.join(f's{i}' for i in range(len(sos)))+' -> y; }'; st.graphviz_chart(dot); st.dataframe(pd.DataFrame(sos,columns=['b0','b1','b2','a0','a1','a2']),hide_index=True); idx=st.selectbox('Xem chi tiết section',range(len(sos)),format_func=lambda i:f'SOS {i+1}'); sb,sa=d.normalize(sos[idx,:3],sos[idx,3:]); st.graphviz_chart(make_graph(sb,sa,'Direct Form II'))
        else: st.info('SOS tắt với FIR bậc cao để tránh phân tích nghiệm kém điều kiện.')
    elif K<=20: st.graphviz_chart(make_graph(b,a,form))
    else: st.info('Sơ đồ đầy đủ chỉ hiển thị tới bậc 20 để dễ đọc. Hệ số vẫn được xử lý.')
    raw=st.text_input('Dãy x[n] để chạy từng mẫu','1, 2, 0, -1, 0, 0');
    try:
        xx=np.array(coeff_input(raw)[:100]); yy,rows=d.df2(xx,b,a,True); cols=['n','x[n]']+[f'w[n-{i}]' for i in range(1,K+1)]+['w[n]','y[n]']; st.dataframe(pd.DataFrame(rows,columns=cols),hide_index=True); st.caption('Bảng trạng thái của Direct Form II chuẩn tắc; w là tín hiệu nội bộ trước dãy trễ.')
    except Exception as e: st.error(str(e))
with tabs[5]:
    st.subheader('Lọc dữ liệu thực tế — trước / sau')
    if x is None: st.info('Chọn tệp hoặc ghi âm ở thanh bên.')
    elif stable_native:
        engine=st.selectbox('Engine xử lý',['Tối ưu SciPy (SOS nếu có)','Tự lập trình DF-I','Tự lập trình DF-II','Tự lập trình Cascade SOS']); run=st.button('▶ Thực hiện lọc',type='primary')
        # Keep output only while all inputs match; avoids stale results on rerun.
        import hashlib
        sig=hashlib.sha256(x.tobytes()+b.tobytes()+a.tobytes()+str((x.shape,fs,engine)).encode()+(sos.tobytes() if sos is not None else b'')).hexdigest()
        if run:
            try:
                start=time.perf_counter()
                if engine=='Tối ưu SciPy (SOS nếu có)': y=signal.sosfilt(sos,x,axis=0) if sos is not None else signal.lfilter(b,a,x,axis=0)
                else:
                    if x.size>200000: raise ValueError('Engine Python tự viết giới hạn 200.000 mẫu tổng; dùng engine tối ưu cho tệp dài.')
                    if engine.endswith('SOS') and sos is None: raise ValueError('Không có SOS.')
                    fn={'Tự lập trình DF-I':lambda v:d.df1(v,b,a),'Tự lập trình DF-II':lambda v:d.df2(v,b,a),'Tự lập trình Cascade SOS':lambda v:d.cascade(v,sos)}[engine]; y=np.column_stack([fn(v) for v in x.T])
                if not np.all(np.isfinite(y)): raise ValueError('Kết quả tràn số; thử SOS hoặc giảm bậc.')
                st.session_state['result']=(sig,y,time.perf_counter()-start)
            except Exception as e: st.error(str(e))
        result=st.session_state.get('result')
        if result and result[0]==sig:
            _,y,dt=result; c=st.columns(3); c[0].metric('Thời lượng',f'{len(x)/fs:.2f} s'); c[1].metric('Thời gian tính',f'{dt*1000:.2f} ms'); c[2].metric('Kênh',x.shape[1]); ch=st.selectbox('Kênh hiển thị',range(x.shape[1]),format_func=lambda i:f'Kênh {i+1}'); stride=max(1,len(x)//16000); t=np.arange(len(x))[::stride]/fs; chart(t,[('Trước',x[::stride,ch]),('Sau',y[::stride,ch])],'s','Biên độ','wave'); f,px=d.spectrum(x[:,ch],fs); _,py=d.spectrum(y[:,ch],fs); chart(f,[('Trước',px),('Sau',py)],'Hz','PSD (dB/Hz)','psd')
            c=st.columns(2); c[0].metric('RMS trước',f'{np.sqrt(np.mean(x*x)):.5g}'); c[1].metric('RMS sau',f'{np.sqrt(np.mean(y*y)):.5g}')
            lo=st.number_input('Dải đánh giá từ Hz',0.,float(fs/2),0.); hi=st.number_input('Đến Hz',0.,float(fs/2),min(100.,fs/2)); mask=(f>=lo)&(f<=hi)
            if mask.any() and hi>lo: st.write(f'Thay đổi công suất dải (sau/trước): {10*np.log10(max(np.sum(10**(py[mask]/10)),1e-24)/max(np.sum(10**(px[mask]/10)),1e-24)):.3f} dB')
            if ref is not None: st.write(f'SNR so với tín hiệu sạch đã biết, chưa bù trễ: {d.snr(ref,x):.2f} → {d.snr(ref,y):.2f} dB')
            else: st.caption('Không tính SNR thật khi không có tín hiệu sạch tham chiếu.')
            if audio:
                scale=1/max(1.,np.max(np.abs(x)),np.max(np.abs(y))); c=st.columns(2); c[0].write('Âm thanh gốc'); c[0].audio(d.wav_bytes(x,fs,scale)); c[1].write('Âm thanh sau lọc'); c[1].audio(d.wav_bytes(y,fs,scale)); st.caption(f'Cùng hệ số gain phát/xuất {scale:.5g} để không clipping; WAV PCM16.'); st.download_button('Xuất WAV sau lọc',d.wav_bytes(y,fs,scale),'filtered.wav','audio/wav')
            if x.size<=500000:
                out=pd.DataFrame(np.column_stack((np.arange(len(y))/fs,x,y)),columns=['time_s']+[f'input_{i+1}' for i in range(x.shape[1])]+[f'output_{i+1}' for i in range(y.shape[1])]); st.download_button('Xuất CSV trước/sau',out.to_csv(index=False),'signals.csv','text/csv')
            else: st.caption('Xuất CSV giới hạn 500.000 mẫu tổng để tránh tệp quá lớn.')
        else: st.info('Nhấn Thực hiện lọc để cập nhật kết quả.')
with tabs[6]:
    st.subheader('Đối chiếu cấu trúc và ảnh hưởng lượng tử hệ số')
    if stable_native:
        N=st.slider('Mẫu benchmark',128,4096,1024); inp=np.random.default_rng(7).normal(0,.1,N); expected=signal.lfilter(b,a,inp); records=[]
        methods=[('DF-I',lambda:d.df1(inp,b,a)),('DF-II',lambda:d.df2(inp,b,a))]+([('SOS tự viết',lambda:d.cascade(inp,sos)),('SOS SciPy',lambda:signal.sosfilt(sos,inp))] if sos is not None else [])
        for name,fn in methods:
            start=time.perf_counter(); out=fn(); elapsed=(time.perf_counter()-start)*1000; err=np.max(np.abs(out-expected)); records.append([name,elapsed,err,'Đạt' if np.allclose(out,expected,rtol=1e-6,atol=1e-8) else 'Sai khác số'])
        st.dataframe(pd.DataFrame(records,columns=['Cấu trúc','Thời gian (ms)','Sai số tuyệt đối max vs lfilter','So khớp']),hide_index=True); st.caption('Benchmark Python trên máy hiện tại, không phải thời gian của chip DSP. lfilter cũng có thể kém chính xác ở bậc cao.')
        bits=st.slider('Bit phần lẻ của hệ số',2,24,8); bq=np.round(b*2**bits)/2**bits; aq=np.round(a*2**bits)/2**bits; _,pq=d.poles_zeros(bq,aq); rq=max(np.abs(pq),default=0.); st.write(f'Bán kính cực b/a trước: {radius:.6g} | sau: {rq:.6g} → '+('ổn định' if rq<1 else 'không ổn định'))
        if rq<1:
            _,hz,H0=d.response(b,a,fs); _,_,Hq=d.response(bq,aq,fs); chart(hz,[('Gốc',d.db(H0)),('Lượng tử hệ số',d.db(Hq))],'Hz','dB','quant')
        st.caption('Chỉ làm tròn hệ số, không mô phỏng tràn, bão hòa hay lượng tử trạng thái fixed-point.')
st.divider(); st.caption('DSP Filter Studio • Xử lý offline trên máy local • Chương 6: H(z), pole-zero, đáp ứng tần số, phân loại, sin/cos, hiện thực.')
