"""DSP algorithms, causal systems, zero initial conditions. Coefficients in z^-1."""
import numpy as np
from scipy import signal


def normalize(b, a):
    b, a = np.asarray(b, float), np.asarray(a, float)
    if b.ndim != 1 or a.ndim != 1 or not len(b) or not len(a) or not np.all(np.isfinite(np.r_[b,a])) or a[0] == 0:
        raise ValueError('Hệ số không hợp lệ; a0 phải khác 0.')
    b, a = np.trim_zeros(b/a[0], 'b'), np.trim_zeros(a/a[0], 'b')
    return (b if len(b) else np.array([0.])), a


def poles_zeros(b,a):
    b,a=normalize(b,a); k=max(len(b),len(a))
    # Equal degree in z, including poles/zeros at origin from delays.
    return (np.roots(np.pad(b,(0,k-len(b)))) if np.any(b) else np.array([]),
            np.roots(np.pad(a,(0,k-len(a)))))


def stable(b,a):
    _,p=poles_zeros(b,a)
    return bool(np.all(np.abs(p)<1))


def sections(b,a):
    b,a=normalize(b,a)
    if not np.any(b):
        return np.array([[0.,0,0,1,0,0]]) if len(a)==1 else sections([1],a)*np.array([0,0,0,1,1,1])
    d=int(np.flatnonzero(b)[0]); b=b[d:]; k=max(len(b),len(a))
    sos=signal.tf2sos(np.pad(b,(0,k-len(b))),np.pad(a,(0,k-len(a))))
    delays=[[0,0,1,1,0,0]]*(d//2)+[[0,1,0,1,0,0]]*(d%2)
    return np.vstack([delays,sos]) if delays else sos


def design(family,kind,order,cut,fs,ripple=1,atten=40):
    if family=='FIR Hamming':
        return signal.firwin(order+1,cut,fs=fs,pass_zero=kind),np.array([1.]),None
    kw={'rp':ripple} if family=='Chebyshev I' else {'rs':atten} if family=='Chebyshev II' else {'rp':ripple,'rs':atten} if family=='Elliptic' else {}
    sos=signal.iirfilter(order,cut,btype=kind,ftype={'Butterworth':'butter','Chebyshev I':'cheby1','Chebyshev II':'cheby2','Elliptic':'ellip'}[family],fs=fs,output='sos',**kw)
    b,a=signal.sos2tf(sos); b,a=normalize(b,a)
    return b,a,sos


def df1(x,b,a):
    b,a=normalize(b,a); x=np.asarray(x,float); y=np.zeros_like(x)
    for n in range(len(x)):
        m=min(n+1,len(b)); k=min(n,len(a)-1)
        y[n]=np.dot(b[:m],x[n-np.arange(m)])-np.dot(a[1:k+1],y[n-np.arange(1,k+1)])
    return y


def df2(x,b,a,trace=False):
    b,a=normalize(b,a); k=max(len(b),len(a))-1
    b=np.pad(b,(0,k+1-len(b))); a=np.pad(a,(0,k+1-len(a)))
    state=np.zeros(k); y=np.zeros(len(x)); rows=[]
    for n,v in enumerate(x):
        w=float(v-np.dot(a[1:],state)); y[n]=b[0]*w+np.dot(b[1:],state)
        if trace: rows.append([n,v,*state,w,y[n]])
        if k: state[1:]=state[:-1]; state[0]=w
    return (y,rows) if trace else y


def cascade(x,sos):
    y=np.asarray(x,float)
    for row in sos: y=df2(y,row[:3],row[3:])
    return y


def response(b,a,fs,n=4096,sos=None):
    w=np.linspace(-np.pi,np.pi,n+1)
    _,h=signal.sosfreqz(sos,worN=w) if sos is not None else signal.freqz(b,a,worN=w)
    return w,w*fs/(2*np.pi),h


def db(x): return 20*np.log10(np.maximum(np.abs(x),1e-12))


def classify(b,a,sos=None):
    _,_,h=response(b,a,2,sos=sos); m=np.abs(h[len(h)//2:]); peak=np.max(m)
    if peak<1e-12: return 'Bộ lọc zero'
    if np.min(m)>0.9*peak: return 'Gần all-pass / gain phẳng'
    floor=np.min(m); span=peak-floor; lo,hi=(m[0]-floor)/span,(m[-1]-floor)/span
    if lo>.9 and hi<.1: return 'Thông thấp (LPF)'
    if lo<.1 and hi>.9: return 'Thông cao (HPF)'
    if lo<.2 and hi<.2: return 'Thông dải (BPF)'
    if lo>.7 and hi>.7: return 'Chắn dải (BSF)'
    return 'Hỗn hợp / chưa đủ tiêu chí tự động'


def formula(coef):
    terms=[]
    for k,v in enumerate(coef):
        if v==0: continue
        body=f'{abs(v):.7g}'+(f'z^{{-{k}}}' if k else '')
        terms.append(('-' if v<0 else '+' if terms else '')+body)
    return ''.join(terms) or '0'


def demo(fs=16000,seconds=4,kind='audio'):
    t=np.arange(int(fs*seconds))/fs; rng=np.random.default_rng(42)
    if kind=='sensor':
        clean=np.sin(2*np.pi*5*t)+.35*np.sin(2*np.pi*9*t); noise=.4*np.sin(2*np.pi*50*t)+.12*rng.normal(size=len(t))
    else:
        env=.65+.35*np.sin(2*np.pi*2*t)**2
        clean=env*(.32*np.sin(2*np.pi*440*t)+.16*np.sin(2*np.pi*880*t)); noise=.18*np.sin(2*np.pi*50*t)+.13*np.sin(2*np.pi*3000*t)+.025*rng.normal(size=len(t))
    return clean+noise,clean


def wav_bytes(x,fs,scale=1):
    import io, soundfile as sf
    buf=io.BytesIO(); sf.write(buf,np.clip(x*scale,-1,1),int(fs),format='WAV',subtype='PCM_16'); return buf.getvalue()


def spectrum(x,fs):
    f,p=signal.welch(x,fs=fs,nperseg=min(len(x),8192),axis=0)
    if p.ndim>1: p=p.mean(axis=1)
    return f,10*np.log10(np.maximum(p,1e-24))


def snr(ref,y):
    return 10*np.log10(max(np.mean(ref**2),1e-24)/max(np.mean((y-ref)**2),1e-24))
