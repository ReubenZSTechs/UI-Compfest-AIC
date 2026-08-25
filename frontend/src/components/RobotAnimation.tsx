import { useEffect, useRef } from "react";

export function RobotAnimation() {
  const displayRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    const display = displayRef.current;
    if (!display) return;

    let offset = 0;
    const pathWidth = 24;

    const smokes = [
      ["   ( )   ", "  ( o )  "],
      ["  ( o )  ", " (  O  ) "],
      [" (  O  ) ", "   ( )   "],
    ];

    function drawFrame() {
      const smoke = smokes[Math.floor(offset / 2) % smokes.length];

      let lineTop = "";
      let lineBody = "";

      for (let i = 0; i < pathWidth; i++) {
        const pos = (i + offset) % 8;
        if (pos === 0) {
          lineTop += " ";
          lineBody += "|";
        } else if (pos === 1 || pos === 2) {
          lineTop += "_";
          lineBody += " ";
        } else if (pos === 3) {
          lineTop += " ";
          lineBody += "|";
        } else {
          lineTop += " ";
          lineBody += " ";
        }
      }

      const art = `                ${smoke[0]}
                ${smoke[1]}
              +------------+
              | [ MACHINE] |
${lineTop}|            |
${lineBody}|   [==]     |
==============================+
==============================
  | |   | |       | |      |   `;

      if (display) {
        display.textContent = art;
      }
      offset = (offset + 1) % 8;
    }

    drawFrame();
    const interval = setInterval(drawFrame, 150);

    return () => clearInterval(interval);
  }, []);

  return (
    <pre
      ref={displayRef}
      style={{
        fontSize: "18px",
        lineHeight: "1.18",
        letterSpacing: "2px",
        whiteSpace: "pre",
        color: "#60a5fa",
        textShadow:
          "0 0 12px rgba(96, 165, 250, 0.65), 0 0 25px rgba(59, 130, 246, 0.45), 0 0 40px rgba(37, 99, 235, 0.25)",
        background: "transparent",
        userSelect: "all",
        margin: 0,
        fontFamily: "'IBM Plex Mono', 'Courier New', monospace",
        padding: "0.5rem",
      }}
    />
  );
}

export default RobotAnimation;
