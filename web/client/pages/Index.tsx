import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff, FileText, X } from "lucide-react";
import hanyangLogo from "../public/hanyang_logo.png";

export default function Index() {
  const [showPassword, setShowPassword] = useState(false);
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [showTermsModal, setShowTermsModal] = useState(false);
  const navigate = useNavigate();

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    
    if (!agreedToTerms) {
      setError("약관에 동의해주세요.");
      return;
    }
    
    // 실제 API로 로그인 요청
    try {
      const res = await fetch("/api/user/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId, password }),
      });
      if (res.ok) {
        navigate("/success", { state: { userId } });
      } else {
        const data = await res.json();
        setError(data.message || "로그인 실패");
      }
    } catch {
      setError("서버 오류");
    }
  };

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-[#87CEEB] to-[#4682B4] flex items-center justify-center p-4">
      <div className="bg-white rounded-[20px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] p-8 w-full max-w-[400px] max-sm:p-6">
        <div className="flex flex-col items-center mb-8">
          <img
            src={hanyangLogo}
            alt="한양대학교 로고"
            className="w-[80px] h-[80px] mb-4 rounded-[12px]"
          />
          <h1 className="text-[24px] font-bold text-[#003366] text-center max-sm:text-[20px]">
            한양대학교 자동화 시스템
          </h1>
        </div>

        <form className="space-y-6" onSubmit={handleSubmit}>
          <div>
            <label className="block text-[14px] font-medium text-[#374151] mb-2">
              아이디
            </label>
            <input
              type="text"
              value={userId}
              onChange={e => setUserId(e.target.value)}
              className="w-full px-4 py-3 border border-[#D1D5DB] rounded-[12px] focus:outline-none focus:ring-2 focus:ring-[#003366] focus:border-transparent text-[16px] max-sm:py-2"
              placeholder="한양대학교 아이디를 입력하세요"
              required
            />
          </div>

          <div>
            <label className="block text-[14px] font-medium text-[#374151] mb-2">
              비밀번호
            </label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-4 py-3 pr-12 border border-[#D1D5DB] rounded-[12px] focus:outline-none focus:ring-2 focus:ring-[#003366] focus:border-transparent text-[16px] max-sm:py-2"
                placeholder="비밀번호를 입력하세요"
                required
              />
              <button
                type="button"
                onClick={togglePasswordVisibility}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#374151] transition-colors duration-200"
              >
                {!showPassword ? (
                  <Eye className="w-5 h-5" />
                ) : (
                  <EyeOff className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>

          {/* 약관 동의 섹션 */}
          <div className="space-y-3">
            <div className="flex items-start space-x-3">
              <input
                type="checkbox"
                id="terms"
                checked={agreedToTerms}
                onChange={(e) => setAgreedToTerms(e.target.checked)}
                className="mt-1 w-4 h-4 text-[#003366] border-[#D1D5DB] rounded focus:ring-[#003366] focus:ring-2"
              />
              <div className="flex-1">
                <label htmlFor="terms" className="text-sm text-[#374151] cursor-pointer">
                  <span className="text-[#003366] font-medium">이용약관</span> 및{" "}
                  <span className="text-[#003366] font-medium">개인정보처리방침</span>에 동의합니다.
                </label>
                <div className="flex space-x-2 mt-2">
                  <button
                    type="button"
                    onClick={() => setShowTermsModal(true)}
                    className="flex items-center space-x-1 text-xs text-[#003366] hover:text-[#002244] underline"
                  >
                    <FileText className="w-3 h-3" />
                    <span>약관 보기</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          {error && <div className="text-red-500 text-sm">{error}</div>}

          <button
            type="submit"
            disabled={!agreedToTerms}
            className={`w-full py-3 rounded-[12px] font-semibold text-[16px] transition-colors duration-200 max-sm:py-2 ${
              agreedToTerms
                ? "bg-[#003366] text-white hover:bg-[#002244]"
                : "bg-[#D1D5DB] text-[#9CA3AF] cursor-not-allowed"
            }`}
          >
            로그인
          </button>
        </form>
      </div>

      {/* 약관 모달 */}
      {showTermsModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-[20px] max-w-2xl w-full max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-6 border-b border-[#E5E7EB]">
              <h2 className="text-xl font-bold text-[#003366]">이용약관 및 개인정보처리방침</h2>
              <button
                onClick={() => setShowTermsModal(false)}
                className="text-[#6B7280] hover:text-[#374151] transition-colors duration-200"
              >
                <X className="w-6 h-6" />
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[60vh] space-y-6">
              {/* 이용약관 */}
              <div>
                <h3 className="text-lg font-semibold text-[#003366] mb-3">제1조 (목적)</h3>
                <p className="text-sm text-[#374151] leading-relaxed">
                  본 약관은 한양대학교 자동화 시스템(이하 "서비스")의 이용과 관련하여 서비스 제공자와 이용자 간의 권리, 의무 및 책임사항, 기타 필요한 사항을 규정함을 목적으로 합니다.
                </p>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-[#003366] mb-3">제2조 (정의)</h3>
                <p className="text-sm text-[#374151] leading-relaxed">
                  1. "서비스"라 함은 한양대학교 녹화 학습 자동 재생 시스템을 의미합니다.<br/>
                  2. "이용자"라 함은 서비스에 접속하여 본 약관에 따라 서비스를 이용하는 회원을 의미합니다.
                </p>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-[#003366] mb-3">제3조 (서비스 이용)</h3>
                <p className="text-sm text-[#374151] leading-relaxed">
                  1. 서비스 이용은 서비스의 자유로운 이용을 원칙으로 합니다.<br/>
                  2. 이용자는 서비스를 이용함에 있어서 관련 법령 및 본 약관을 준수해야 합니다.
                </p>
              </div>

              {/* 개인정보처리방침 */}
              <div className="border-t border-[#E5E7EB] pt-6">
                <h3 className="text-lg font-semibold text-[#003366] mb-3">개인정보처리방침</h3>
                <p className="text-sm text-[#374151] leading-relaxed mb-3">
                  서비스와 그 운영 주체는 개인정보보호법에 따라 이용자의 개인정보 보호 및 권익을 보호하고 개인정보와 관련한 이용자의 고충을 원활하게 처리할 수 있도록 다음과 같은 처리방침을 두고 있습니다.
                </p>
                
                <div className="space-y-2">
                  <p className="text-sm text-[#374151]">
                    <strong>1. 개인정보의 처리목적:</strong> 서비스 제공 및 이용자 관리
                  </p>
                  <p className="text-sm text-[#374151]">
                    <strong>2. 개인정보의 보유기간:</strong> 서비스 이용 종료 시까지
                  </p>
                  <p className="text-sm text-[#374151]">
                    <strong>3. 개인정보의 제3자 제공:</strong> 제공하지 않음
                  </p>
                  <p className="text-sm text-[#374151]">
                    <strong>4. 이용자의 권리:</strong> 개인정보 열람, 정정, 삭제, 처리정지 요구 가능
                  </p>
                </div>
              </div>

              {/* 권리 및 의무 */}
              <div className="border-t border-[#E5E7EB] pt-6">
                <h3 className="text-lg font-semibold text-[#003366] mb-3">이용자의 권리 및 의무</h3>
                <div className="space-y-2">
                  <p className="text-sm text-[#374151]">
                    <strong>권리:</strong>
                  </p>
                  <ul className="text-sm text-[#374151] ml-4 space-y-1">
                    <li>• 서비스 이용권</li>
                    <li>• 개인정보 보호권</li>
                    <li>• 서비스 개선 요구권</li>
                  </ul>
                  
                  <p className="text-sm text-[#374151] mt-3">
                    <strong>의무:</strong>
                  </p>
                  <ul className="text-sm text-[#374151] ml-4 space-y-1">
                    <li>• 관련 법령 및 약관 준수의무</li>
                    <li>• 서비스 이용 시 부정사용 금지</li>
                    <li>• 타인의 권리 침해 금지</li>
                  </ul>
                </div>
              </div>
            </div>
            
            <div className="p-6 border-t border-[#E5E7EB] bg-[#F9FAFB]">
              <button
                onClick={() => setShowTermsModal(false)}
                className="w-full bg-[#003366] text-white py-3 rounded-[12px] font-semibold hover:bg-[#002244] transition-colors duration-200"
              >
                확인
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
