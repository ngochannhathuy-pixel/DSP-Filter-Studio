# DSP Filter Studio v1.0

Bài tập lớn Xử lý số tín hiệu – Chương 6: Hàm truyền và hiện thực bộ lọc (HCMUT).

## Chạy trên Windows bằng VS Code

1. Giải nén toàn bộ ZIP, mở thư mục DSP_Filter_Studio bằng File > Open Folder.
2. Cài Python 3.11 hoặc 3.12 64-bit từ https://www.python.org/downloads/ (chọn Add python.exe to PATH nếu có). Cài extension Python của Microsoft trong VS Code (Ctrl+Shift+X).
3. Mở Terminal > New Terminal. Chạy `py --version` để kiểm tra. Nếu không có `py`, thử `python --version`.
4. Chạy từng dòng sau trong PowerShell. Không cần bật activation script hay chỉnh Execution Policy:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -v test_dsp
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Nếu dùng Python 3.11, thay `-3.12` thành `-3.11`. Nếu chỉ có lệnh python, dùng `python -m venv .venv`.
5. Trình duyệt mở http://localhost:8501. Dừng bằng Ctrl+C tại Terminal. Sau lần đầu chỉ cần chạy dòng streamlit.
6. Ctrl+Shift+P > Python: Select Interpreter > chọn `.venv\Scripts\python.exe`. Không chỉnh sửa thư mục .venv.

Có thể dùng `run.bat` sau khi đã tạo môi trường và cài gói. Internet cần cho cài đặt lần đầu, không cần cho tính toán offline. Microphone yêu cầu quyền ghi âm của trình duyệt. MP3 phụ thuộc libsndfile; nếu lỗi hãy dùng WAV hoặc FLAC.

## Cách sử dụng

- Sidebar chọn nguồn dữ liệu và cách tạo bộ lọc. Nhập hệ số b, a theo thứ tự z^-k; dấu hồi tiếp là -a[k].
- Tab 01: H(z), phương trình sai phân, hệ số JSON.
- Tab 02: cực-zero, ROC nhân quả, ổn định. Không tự triệt cực-zero; cảnh báo về độ ổn định của hiện thực chưa tối giản.
- Tab 03: h[n], đáp ứng bước, biên độ dB, pha, group delay, phân loại gần đúng.
- Tab 04: đáp ứng xác lập sin/cos và kết quả với trạng thái đầu 0.
- Tab 05: DF-I, DF-II, SOS, sơ đồ động và bảng trạng thái w[n] DF-II.
- Tab 06: bấm Thực hiện lọc; xem waveform, PSD, RMS, suy giảm công suất trong dải và SNR nếu có tham chiếu. Nghe trước/sau và xuất WAV/CSV.
- Tab 07: benchmark và lượng tử hệ số (không mô phỏng đầy đủ fixed-point).

## Kịch bản thuyết trình

### A. Kiểm tra lý thuyết Chương 6
- Chọn Nhập hệ số H(z), b = 0, 1; a = 1, -0.5 (Bài tập 4 trong slide).
- H(z) = z^-1/(1-0.5z^-1), y[n]=x[n-1]+0.5y[n-1].
- Cực 0.5; ROC |z|>0.5; ổn định với giả thiết nhân quả.
- h[n] = 0.5^(n-1)u[n-1]; h[0:5] = 0,1,0.5,0.25,0.125.
- Gain tại DC 2; gain tại Nyquist 2/3; thông thấp.
- Direct I cần 2 trễ; Direct II cần 1 trễ. Hai cấu trúc cho cùng kết quả trong số học chính xác.
- Đổi a thành 1,-1.1 để minh họa cực nằm ngoài vòng đơn vị (không thực hiện lọc âm thanh).

### B. Tín hiệu tổng hợp có tham chiếu
- Chọn Demo âm thanh tổng hợp, Fs=16 kHz; tín hiệu gồm tone 440, 880 Hz và nhiễu 50, 3000 Hz + nhiễu trắng.
- Chọn Butterworth thông thấp bậc 4 fc=1200 Hz; quan sát nhiễu 3000 Hz suy giảm nhưng hum 50 Hz còn.
- Chọn Notch 50 Hz Q=30; quan sát vùng 50 Hz suy giảm nhưng nhiễu 3000 Hz còn.
- Demo âm thanh này là tone tổng hợp, không phải giọng nói thu thật. Tệp noisy/clean trong samples dùng để đối chiếu.

### C. Ghi âm thực tế
- Ghi khoảng 5–10 giây bằng điện thoại hoặc microphone. Có thể thử với môi trường có tiếng quạt, ù điện, hoặc chủ động thêm nhiễu 50 Hz vào bản sao âm thanh để kiểm chứng.
- Chọn Tệp âm thanh hoặc Microphone, sau đó chọn preset Giọng nói 300–3400 Hz + notch 50 Hz hoặc Notch 50 Hz.
- Bấm lọc, so sánh phổ PSD, độ suy giảm vùng nhiễu, nghe A/B, xuất WAV. Không khẳng định SNR thật nếu không có bản ghi sạch tham chiếu. Lọc theo tần số không loại được nhiễu chồng dải với tiếng nói.

### D. Cảm biến
- Chọn Demo cảm biến tổng hợp hoặc CSV mẫu `samples/demo_sensor.csv`, Fs=200 Hz, cột signal.
- Chọn Butterworth thông thấp fc=12 Hz, bậc 4. Tín hiệu hữu ích gồm 5 và 9 Hz; nhiễu 50 Hz + nhiễu trắng.
- So sánh PSD, độ suy giảm vùng 45–55 Hz. Thử dữ liệu thật từ cảm biến lấy mẫu đều.

## Cấu trúc mã
- app.py: UI, nguồn dữ liệu, đồ thị, sơ đồ khối, xuất dữ liệu.
- dsp_core.py: thuật toán DSP, DF-I, DF-II, cascade, thiết kế, phân tích.
- test_dsp.py: 5 nhóm test, trong đó có 8 trường hợp hiện thực và 20 tổ hợp thiết kế.
- TEST_RESULTS.txt: kết quả kiểm tra trên môi trường tạo file.
- samples/: dữ liệu tổng hợp, không phải dữ liệu hiện trường.

## Giới hạn bản v1.0
- Lọc offline hoặc ghi âm rồi lọc; chưa streaming trực tiếp với latency cam kết.
- Tối đa 120 giây, 2 triệu mẫu mỗi kênh, 8 kênh, file upload 50 MB. Engine Python tự viết giới hạn 200 nghìn mẫu tổng. CSV xuất giới hạn 500 nghìn mẫu tổng.
- Bậc thiết kế IIR tối đa 6 (bandpass/stop bậc thực gấp đôi); FIR tối đa 80. FIR highpass/bandstop yêu cầu số taps lẻ (bậc chẵn). SOS từ đa thức chỉ thực hiện tới bậc 24; bậc cao có thể kém điều kiện. Sơ đồ trực tiếp đầy đủ tới bậc 20.
- Hệ số thực, hệ nhân quả, điều kiện đầu bằng 0. Chưa hỗ trợ ROC hai phía hoặc phi nhân quả, chưa xuất mã cho kit DSP. Chỉ phân tích số học dấu chấm động và lượng tử hệ số.
- Kiểm tra thuật toán thành công; UI Streamlit chưa được chạy trực tiếp trong môi trường tạo file vì không có sẵn Streamlit và không cài được từ kho gói. Cần chạy trên máy người dùng để xác nhận giao diện, trình duyệt, quyền microphone.

## Nguồn học thuật
- TS. Nguyễn Chí Ngọc, DSP-Chapter6_student_2024.pptx, slide 2–18, bài tập 4 slide 22.
- Bộ môn Viễn thông, HCMUT, Tài liệu thí nghiệm Xử lý số tín hiệu (2015), Bài 3 và Bài 6.
- Streamlit: https://docs.streamlit.io/get-started/installation/command-line
