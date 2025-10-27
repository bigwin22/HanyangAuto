import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff, FileText, X, Loader2 } from "lucide-react";
import hanyangLogo from "../public/hanyang_logo.png";

export default function Index() {
  const [showPassword, setShowPassword] = useState(false);
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [showTermsModal, setShowTermsModal] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyStatus, setVerifyStatus] = useState("");
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

    setIsVerifying(true);

    try {
      // 1단계: 계정 검증
      setVerifyStatus("계정을 확인하는 중입니다...");
      const verifyRes = await fetch("/api/user/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId, password }),
      });

      const verifyData = await verifyRes.json();

      if (!verifyData.success) {
        setError(verifyData.message || "아이디 또는 비밀번호가 올바르지 않습니다.");
        setIsVerifying(false);
        return;
      }

      // 2단계: 검증 성공, 실제 등록 진행
      setVerifyStatus("계정 인증 성공! 등록을 진행하고 있습니다...");
      const loginRes = await fetch("/api/user/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId, password }),
      });

      if (loginRes.ok) {
        navigate("/success", { state: { userId } });
      } else {
        const loginData = await loginRes.json();
        setError(loginData.message || "등록 중 오류가 발생했습니다.");
        setIsVerifying(false);
      }
    } catch {
      setError("서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.");
      setIsVerifying(false);
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
            {isVerifying ? "계정 검증 중" : "한양대학교 자동화 시스템"}
          </h1>
        </div>

        {isVerifying ? (
          // 로딩 화면
          <div className="space-y-6 text-center">
            <div className="flex justify-center">
              <Loader2 className="w-16 h-16 text-[#003366] animate-spin" />
            </div>
            <div className="text-[16px] text-[#374151] font-medium">
              {verifyStatus}
            </div>
            <div className="text-[14px] text-[#6B7280]">
              잠시만 기다려 주세요.
            </div>
          </div>
        ) : (
          // 로그인 폼
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
        )}

        {/* Copyright 정보 */}
        <div className="mt-8 text-center">
          <p className="text-xs text-[#6B7280]">
            © 2025 newme.dev. All rights reserved.
          </p>
          <p className="text-xs text-[#9CA3AF] mt-1">
            한양대학교 녹화 학습 자동 재생 시스템
          </p>
        </div>
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
            
            <div className="p-6 overflow-y-auto max-h-[60vh] space-y-6 text-sm text-[#374151] leading-relaxed">
              {/* 이용약관 */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-[#003366]">이용약관</h3>
                
                <p className="font-bold">제1조 (목적)</p>
                <p>본 약관은 '한양대학교 자동화 시스템'(이하 "서비스")의 이용과 관련하여 서비스 제공자와 이용자 간의 권리, 의무 및 책임사항, 기타 필요한 사항을 규정함을 목적으로 합니다.</p>

                <p className="font-bold">제2조 (정의)</p>
                <ul className="list-disc ml-5 space-y-1">
                  <li>"서비스"라 함은 한양대학교 온라인 강의의 자동 재생을 지원하는 시스템 및 관련 모든 부대 서비스를 의미합니다.</li>
                  <li>"이용자"라 함은 본 약관에 동의하고 서비스를 이용하기 위해 자신의 한양대학교 계정 정보(ID, 비밀번호)를 제공한 자를 의미합니다.</li>
                  <li>"계정 정보"라 함은 이용자가 제공한 한양대학교 포털 ID와 비밀번호를 의미합니다.</li>
                </ul>

                <p className="font-bold">제3조 (서비스의 제공 및 변경)</p>
                <ul className="list-disc ml-5 space-y-1">
                  <li>서비스는 연중무휴, 1일 24시간 제공함을 원칙으로 하나, 서버 점검, 기술적 문제, 기타 불가항력적인 사유가 발생할 경우 일시적으로 중단될 수 있습니다.</li>
                  <li>서비스 제공자는 서비스의 내용, 운영상 또는 기술상의 필요에 따라 제공하고 있는 서비스의 전부 또는 일부를 변경할 수 있으며, 이에 대해 약관에서 정한 방법으로 이용자에게 공지합니다.</li>
                </ul>

                <p className="font-bold">제4조 (이용자의 의무 및 책임)</p>
                <ul className="list-disc ml-5 space-y-1">
                  <li>이용자는 자신의 계정 정보를 정확하게 제공해야 하며, 정보의 부정확함으로 인해 발생하는 문제의 책임은 이용자 본인에게 있습니다.</li>
                  <li>이용자는 자신의 계정 정보를 안전하게 관리할 책임이 있으며, 사용자의 부주의에 의한 계정 정보 유출의 모든 책임은 이용자에게 있습니다.</li>
                  <li>이용자는 본 서비스를 학업 활동 보조 목적으로만 사용해야 하며, 학칙 및 관련 규정을 준수할 의무가 있습니다.</li>
                  <li>서비스 이용 결과(예: 출석 인정 여부, 성적 등)에 대한 최종 확인 책임은 이용자 본인에게 있습니다. 서비스는 보조 수단일 뿐이며, 출석 결과를 보장하지 않습니다.</li>
                </ul>

                <p className="font-bold">제5조 (면책 조항)</p>
                <ul className="list-disc ml-5 space-y-1">
                  <li>서비스 제공자는 천재지변, 한양대학교 시스템의 변경 또는 오류, 통신 장애 등 불가항력적인 사유로 인해 서비스를 제공할 수 없는 경우 책임이 면제됩니다.</li>
                  <li>서비스 제공자는 이용자의 귀책사유(예: 계정 정보 오기입, 학칙 위반)로 인한 서비스 이용 장애나 불이익에 대하여 책임을 지지 않습니다.</li>
                  <li>본 서비스는 "있는 그대로(As-Is)" 및 "이용 가능한 대로(As-Available)" 제공됩니다. 서비스 제공자는 서비스의 완전성, 안정성, 정확성, 특정 목적에의 적합성을 보증하지 않습니다.</li>
                  <li>서비스 제공자는 서비스 이용과 관련하여 이용자에게 발생한 어떠한 학업적 불이익(예: 출석 미인정, 성적 불이익)이나 기타 간접적, 부수적, 특별 또는 결과적 손해에 대해서도 법률이 허용하는 최대 범위 내에서 책임을 지지 않습니다.</li>
                  <li>서비스의 사용 여부에 대한 결정은 전적으로 이용자의 자율적인 판단에 따르며, 그로 인해 발생하는 모든 책임은 이용자 본인에게 있습니다.</li>
                </ul>

                <p className="font-bold">제6조 (이용자에 대한 통지)</p>
                <ul className="list-disc ml-5 space-y-1">
                  <li>서비스 제공자가 이용자에 대한 통지를 하는 경우, 본 약관에 별도 규정이 없는 한 이용자가 제공한 ID를 기반으로 한 한양대학교 이메일 주소로 할 수 있습니다.</li>
                  <li>서비스 제공자는 불특정 다수 이용자에 대한 통지의 경우, 서비스의 공지사항 화면에 게시함으로써 개별 통지에 갈음할 수 있습니다.</li>
                </ul>
              </div>

              {/* 개인정보처리방침 */}
              <div className="border-t border-[#E5E7EB] pt-6 space-y-4">
                <h3 className="text-lg font-semibold text-[#003366]">개인정보처리방침</h3>
                
                <p>서비스 제공자는 개인정보보호법 등 관련 법령을 준수하며, 이용자의 개인정보 보호를 위해 최선을 다하고 있습니다.</p>

                <p className="font-bold">1. 개인정보의 수집 및 이용 목적</p>
                <p>서비스는 다음의 목적을 위해 개인정보를 수집하고 이용합니다.</p>
                <ul className="list-disc ml-5 space-y-1">
                  <li>한양대학교 온라인 강의 자동 재생 기능 수행</li>
                  <li>서비스 관련 고지사항 전달 및 이용자 문의 응대</li>
                </ul>

                <p className="font-bold">2. 수집하는 개인정보 항목</p>
                <ul className="list-disc ml-5 space-y-1">
                  <li>필수항목: 한양대학교 포털 ID, 암호화된 비밀번호</li>
                </ul>

                <p className="font-bold">3. 개인정보의 보유 및 이용기간</p>
                <p>이용자의 개인정보는 서비스 이용 계약이 유지되는 동안 보유 및 이용됩니다. 이용자가 회원 탈퇴를 요청하거나 개인정보 수집 및 이용에 대한 동의를 철회하는 경우, 해당 개인정보를 지체 없이 파기합니다.</p>

                <p className="font-bold">4. 개인정보의 제3자 제공</p>
                <p>서비스 제공자는 이용자의 개인정보를 원칙적으로 외부에 제공하지 않습니다. 다만, 법령의 규정에 의거하거나 수사 목적으로 법령에 정해진 절차와 방법에 따라 수사기관의 요구가 있는 경우는 예외로 합니다.</p>

                <p className="font-bold">5. 개인정보의 안전성 확보 조치</p>
                <p>서비스 제공자는 이용자의 비밀번호를 암호화하여 저장 및 관리하고 있으며, 해킹이나 컴퓨터 바이러스 등에 의한 개인정보 유출 및 훼손을 막기 위하여 보안 프로그램을 설치하고 주기적인 갱신·점검을 하는 등 기술적/관리적 보호 대책을 강구하고 있습니다. 만일 개인정보 유출 사고가 발생하는 경우, 관련 법령에 따라 이용자에게 통지하고 관계 당국의 조사에 적극적으로 협력하는 등 신속한 조치를 취하겠습니다.</p>

                <p className="font-bold">6. 정보주체의 권리·의무 및 행사방법</p>
                <p>이용자는 언제든지 등록되어 있는 자신의 개인정보를 조회하거나 수정·삭제를 요청할 수 있습니다. 서비스 탈퇴(동의 철회)를 통해 개인정보의 수집 및 이용 동의를 철회할 수 있습니다.</p>
              </div>
            </div>
            
            <div className="p-6 border-t border-[#E5E7EB] bg-[#F9FAFB]">
              <button
                onClick={() => setShowTermsModal(false)}
                className="w-full bg-[#003366] text-white py-3 rounded-[12px] font-semibold hover:bg-[#002244] transition-colors duration-200"
              >
                확인
              </button>
              
              {/* Copyright 정보 */}
              <div className="mt-4 text-center">
                <p className="text-xs text-[#6B7280]">
                  © 2025 newme.dev. All rights reserved.
                  </p>
                <p className="text-xs text-[#9CA3AF] mt-1">
                  한양대학교 녹화 학습 자동 재생 시스템
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
