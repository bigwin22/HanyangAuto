import React from "react";
import { useLocation, useNavigate } from "react-router-dom";

export default function Success() {
  const location = useLocation();
  const navigate = useNavigate();
  // Assume userId is passed via state (e.g., navigate('/success', { state: { userId: 'student001' } }))
  const userId = location.state?.userId || "";

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-[#87CEEB] to-[#4682B4] flex items-center justify-center p-4">
      <div className="bg-white rounded-[20px] shadow-[0_20px_60px_rgba(0,0,0,0.15)] p-8 w-full max-w-[400px] max-sm:p-6">
        <div className="flex flex-col items-center mb-8">
          <img
            src="/hanyang_logo.png"
            alt="한양대학교 로고"
            className="w-[80px] h-[80px] mb-4 rounded-[12px]"
          />
          <h1 className="text-[24px] font-bold text-[#003366] text-center max-sm:text-[20px]">
            계정 등록 완료
          </h1>
        </div>
        <div className="space-y-6 text-center">
          <div className="text-[16px] text-[#374151] font-medium">
            계정이 성공적으로 등록되었습니다.
          </div>
          <div className="text-[16px] text-[#003366] font-bold">
            사용자 아이디: <span className="text-[#2563EB]">{userId}</span>
          </div>
          <div className="text-[15px] text-[#374151]">
            강의가 자동으로 완료 처리될 예정입니다.<br />
            잠시만 기다려 주세요.
          </div>
        </div>
        <button
          onClick={() => navigate("/")}
          className="mt-8 w-full bg-[#003366] text-white py-3 rounded-[12px] font-semibold text-[16px] hover:bg-[#002244] transition-colors duration-200 max-sm:py-2"
        >
          메인으로 돌아가기
        </button>
      </div>
    </div>
  );
} 