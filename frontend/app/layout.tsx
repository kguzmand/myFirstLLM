import { CopilotKit } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html>
      <body>
        <CopilotKit
          runtimeUrl="/api/copilotkit"
          agent="itinerary_agent"
        >
          {children}
        </CopilotKit>
      </body>
    </html>
  );
}