import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatWindow } from "./ChatWindow";
import { DefenseStack } from "./DefenseStack";
import { Heatmap } from "./Heatmap";

describe("Heatmap", () => {
  it("renders one cell per technique x level with the bypass rate", () => {
    render(
      <Heatmap
        techniques={["encoding"]}
        levels={[1, 2]}
        cells={[
          { technique: "encoding", level: 1, attempts: 4, bypass_rate: 0.75 },
          { technique: "encoding", level: 2, attempts: 0, bypass_rate: 0 },
        ]}
      />,
    );
    expect(screen.getByText("Encoding")).toBeInTheDocument();
    expect(screen.getByTestId("cell-encoding-1")).toHaveTextContent("75%");
    expect(screen.getByTestId("cell-encoding-2")).toHaveTextContent("·");
  });

  it("shows an empty state", () => {
    render(<Heatmap techniques={[]} levels={[1]} cells={[]} />);
    expect(screen.getByText(/no attempts/i)).toBeInTheDocument();
  });
});

describe("DefenseStack", () => {
  it("highlights the layer that caught the last attack", () => {
    render(<DefenseStack defenses={["Input filter", "Output filter"]} tripped="Output filter" />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).not.toHaveAttribute("data-tripped");
    expect(items[1]).toHaveAttribute("data-tripped", "true");
  });
});

describe("ChatWindow", () => {
  it("sends trimmed messages and shows blocked replies with the catching layer", async () => {
    const onSend = vi.fn();
    render(
      <ChatWindow
        guardName="Aegis"
        onSend={onSend}
        turns={[
          {
            prompt: "base64 please",
            response: "Blocked",
            blocked: true,
            caughtBy: "output_filter",
            outcome: "blocked",
            techniques: ["encoding"],
          },
        ]}
      />,
    );
    expect(screen.getByText(/caught by: Output filter/i)).toBeInTheDocument();
    expect(screen.getByText("#Encoding")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Message"), "  hello guard  {enter}");
    expect(onSend).toHaveBeenCalledWith("hello guard");
  });
});

describe("ChatWindow notices", () => {
  it("renders rate-limit notices as a status, not a guard block", () => {
    render(
      <ChatWindow
        guardName="Pip"
        onSend={() => {}}
        turns={[{ prompt: "hi", response: "⏳ Easy there! Try again in 3 min.", notice: true }]}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Try again in 3 min");
    expect(screen.queryByText(/caught by/i)).not.toBeInTheDocument();
  });
});
