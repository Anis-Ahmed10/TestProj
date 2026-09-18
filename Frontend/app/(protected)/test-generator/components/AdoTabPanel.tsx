import { Button } from "antd";
import AdoSVG from "../assets/AdoSVG";

export default function AdoTabPanel() {
  return (
    <div className="usi-panel usi-panel-center">
      <div className="usi-not-connected">
        <AdoSVG />
        <div className="usi-not-connected-title">
          Azure DevOps not configured
        </div>
        <p className="usi-not-connected-desc">
          Connect your Azure DevOps organisation to import work items directly.
          An admin must add the ADO integration credentials in project settings
          before this source is available.
        </p>
        <Button disabled size="large">
          Connect Azure DevOps
        </Button>
      </div>
    </div>
  );
}
