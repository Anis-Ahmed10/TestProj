import { Suspense } from "react";
import ProjectViewPage from "./components/ProjectViewPage";

export default function Page() {
  return (
    <Suspense fallback={null}>
      <ProjectViewPage />
    </Suspense>
  );
}
