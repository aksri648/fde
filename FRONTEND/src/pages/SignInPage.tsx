import { onMount } from "solid-js";
import { mountSignIn } from "../auth/clerk";

export default function SignInPage() {
  let container!: HTMLDivElement;

  onMount(() => {
    mountSignIn(container);
  });

  return (
    <div style={{ "min-height": "100vh", display: "flex", "align-items": "center", "justify-content": "center", background: "#09090b" }}>
      <div ref={container!} />
    </div>
  );
}
