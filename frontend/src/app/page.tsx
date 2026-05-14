"use client";

import { useEffect, useState, useRef } from "react";
import { Activity, Camera, Maximize, Cpu, Shield, Zap, Target } from "lucide-react";

interface Status {
  gesture: string;
  gesture_raw: string;
  mode: string;
  tracking_paused: boolean;
  cursor_frozen: boolean;
  fps: number;
  hud_msgs: string[];
}

export default function Dashboard() {
  const [status, setStatus] = useState<Status | null>(null);
  const [logs, setLogs] = useState<{ id: number; msg: string; time: string }[]>([]);
  const logIdRef = useRef(0);
  const lastHudMsgsRef = useRef<string[]>([]);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch("http://localhost:5000/api/status");
        if (res.ok) {
          const data: Status = await res.json();
          setStatus(data);

          // Update logs if new HUD messages arrive
          if (data.hud_msgs && data.hud_msgs.length > 0) {
            const newMsgs = data.hud_msgs.filter(
              (msg) => !lastHudMsgsRef.current.includes(msg)
            );
            if (newMsgs.length > 0) {
              const now = new Date().toLocaleTimeString();
              const newLogEntries = newMsgs.map((msg) => ({
                id: logIdRef.current++,
                msg,
                time: now,
              }));
              setLogs((prev) => [...newLogEntries, ...prev].slice(0, 20)); // Keep last 20
            }
            lastHudMsgsRef.current = data.hud_msgs;
          }
        }
      } catch (err) {
        // console.error("Error fetching status", err);
      }
    };

    const interval = setInterval(fetchStatus, 150); // Fast polling for smooth updates
    return () => clearInterval(interval);
  }, []);

  return (
    <main className="min-h-screen bg-[#030b14] text-[#e0f2fe] p-4 flex flex-col font-mono relative overflow-hidden">
      {/* Background decorations */}
      <div className="absolute top-0 left-0 w-full h-full pointer-events-none opacity-20 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan-900 via-[#030b14] to-[#030b14]" />
      
      {/* Header */}
      <header className="flex justify-between items-center mb-4 z-10 border-b border-cyan-500/30 pb-4">
        <div className="flex items-center gap-3">
          <Shield className="text-cyan-400 w-8 h-8" />
          <h1 className="text-2xl font-bold tracking-widest cyan-glow-text uppercase">
            Gesture Ctrl // Sys.V2
          </h1>
        </div>
        <div className="flex gap-6 text-sm">
          <div className="flex flex-col items-end">
            <span className="text-cyan-600/70">STATUS</span>
            <span className="text-cyan-400 font-bold">ONLINE</span>
          </div>
          <div className="flex flex-col items-end">
            <span className="text-cyan-600/70">UPLINK</span>
            <span className="text-green-400 font-bold">SECURE</span>
          </div>
        </div>
      </header>

      {/* Main Grid */}
      <div className="flex-1 grid grid-cols-12 gap-6 z-10">
        
        {/* Left Panel: Vitals */}
        <div className="col-span-3 flex flex-col gap-4">
          <div className="glass-panel p-4 rounded-lg relative overflow-hidden">
            <div className="absolute top-0 right-0 w-16 h-1 bg-cyan-500/50" />
            <h2 className="text-cyan-500/70 text-xs mb-4 flex items-center gap-2">
              <Cpu className="w-4 h-4" /> CORE VITALS
            </h2>
            <div className="space-y-6">
              <div>
                <div className="text-xs text-cyan-600/80 mb-1">SYSTEM FPS</div>
                <div className="text-4xl cyan-glow-text font-light">
                  {status?.fps || 0}
                  <span className="text-sm text-cyan-500 ml-1">hz</span>
                </div>
              </div>
              <div>
                <div className="text-xs text-cyan-600/80 mb-1">TRACKING MODE</div>
                <div className="text-lg text-cyan-300 border-l-2 border-cyan-500 pl-3">
                  {status?.mode || "INITIALIZING"}
                </div>
              </div>
              <div>
                <div className="text-xs text-cyan-600/80 mb-1">LATEST GESTURE</div>
                <div className="text-xl text-yellow-400 uppercase tracking-wider">
                  {status?.gesture || "—"}
                </div>
              </div>
            </div>
          </div>

          <div className="glass-panel p-4 rounded-lg flex-1">
             <h2 className="text-cyan-500/70 text-xs mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4" /> SYSTEM STATE
            </h2>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm">Engine Status</span>
                <span className={status?.tracking_paused ? "text-red-400" : "text-green-400"}>
                  {status?.tracking_paused ? "PAUSED" : "ACTIVE"}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Cursor Lock</span>
                <span className={status?.cursor_frozen ? "text-cyan-400" : "text-gray-500"}>
                  {status?.cursor_frozen ? "ENGAGED" : "FREE"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Center Panel: Video Feed */}
        <div className="col-span-6 flex flex-col relative">
          <div className="glass-panel flex-1 rounded-lg relative overflow-hidden flex items-center justify-center p-1">
            {/* Corner decorations */}
            <div className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-cyan-400" />
            <div className="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-cyan-400" />
            <div className="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-cyan-400" />
            <div className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-cyan-400" />
            
            <div className="scanline" />
            <div className="absolute top-4 left-4 flex gap-2 items-center z-20 bg-black/50 px-2 py-1 rounded">
              <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              <span className="text-xs text-cyan-500 tracking-widest font-bold">REC</span>
            </div>
            
            {/* The Video Stream */}
            <img 
              src="http://localhost:5000/api/video_feed" 
              alt="Live Hand Tracking Feed"
              className="w-full h-full object-cover filter contrast-125 saturate-50"
            />
            
            {/* Reticle overlay */}
            <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 opacity-30 pointer-events-none">
               <Target className="w-32 h-32 text-cyan-500" strokeWidth={1} />
            </div>
          </div>
        </div>

        {/* Right Panel: Action Log */}
        <div className="col-span-3 flex flex-col gap-4">
          <div className="glass-panel p-4 rounded-lg flex-1 flex flex-col relative overflow-hidden">
             <div className="absolute top-0 right-0 w-16 h-1 bg-cyan-500/50" />
             <h2 className="text-cyan-500/70 text-xs mb-4 flex items-center gap-2">
              <Zap className="w-4 h-4" /> ACTION LOG
            </h2>
            <div className="flex-1 overflow-y-auto space-y-2 text-sm pr-2 custom-scrollbar">
              {logs.length === 0 ? (
                <div className="text-cyan-800/50 text-center mt-10 italic">Awaiting inputs...</div>
              ) : (
                logs.map((log) => (
                  <div key={log.id} className="border-b border-cyan-900/50 pb-2 mb-2 animate-in fade-in slide-in-from-right-4">
                    <div className="text-[10px] text-cyan-600/70">{log.time}</div>
                    <div className="text-cyan-100">{log.msg}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

      </div>
    </main>
  );
}
