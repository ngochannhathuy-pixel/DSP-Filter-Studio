import unittest
import numpy as np
from scipy import signal
import dsp_core as d

class TestDSP(unittest.TestCase):
    def test_realizations(self):
        x=np.random.default_rng(1).normal(size=500)
        cases=[([0,1],[1,-.5]),([1,-1],[1]),([0,0,2],[1,.2,.1]),([1,2,1],[1,-.4]),([1],[1,-.4,.1]),([0],[1]),([0],[1,-.5]),([1],[1])]
        for b,a in cases:
            with self.subTest(b=b,a=a):
                b,a=d.normalize(b,a); s=d.sections(b,a); y=signal.lfilter(b,a,x)
                for v in [d.df1(x,b,a),d.df2(x,b,a),d.cascade(x,s),signal.sosfilt(s,x)]: np.testing.assert_allclose(v,y,atol=1e-10)
    def test_ch6(self):
        b,a=[0,1],[1,-.5]; z,p=d.poles_zeros(b,a)
        np.testing.assert_allclose(p,[.5]); self.assertEqual(len(z),0)
        np.testing.assert_allclose(d.df2([1,0,0,0],b,a),[0,1,.5,.25]); self.assertTrue(d.stable(b,a)); self.assertFalse(d.stable([1],[1,-1]))
        self.assertEqual(d.classify(b,a),'Thông thấp (LPF)')
    def test_design(self):
        for family in ['Butterworth','FIR Hamming','Chebyshev I','Chebyshev II','Elliptic']:
            for kind,cut in [('lowpass',1000),('highpass',1000),('bandpass',[300,1500]),('bandstop',[300,1500])]:
                b,a,s=d.design(family,kind,4,cut,8000); self.assertTrue(d.stable(b,a)); self.assertTrue(np.all(np.isfinite(d.response(b,a,8000,sos=s)[2])))
    def test_notch(self):
        b,a=signal.iirnotch(50,30,fs=16000); _,H=signal.freqz(b,a,worN=[2*np.pi*50/16000,2*np.pi*440/16000]); self.assertLess(abs(H[0]),1e-8); self.assertGreater(abs(H[1]),.99)
    def test_audio(self):
        import io,soundfile as sf
        x,ref=d.demo(); y,fs=sf.read(io.BytesIO(d.wav_bytes(x,16000))); self.assertEqual(fs,16000); self.assertEqual(len(x),len(y)); np.testing.assert_allclose(x,y,atol=1/32768)

if __name__=='__main__': unittest.main(verbosity=2)
