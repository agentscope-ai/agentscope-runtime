import { SparkSettingLine } from "@agentscope-ai/icons";
import { IconButton, Drawer } from "@agentscope-ai/design";
import { useState } from "react";
import OptionsEditor from "./OptionsEditor";

interface OptionsPanelProps {
  value?: any;
  onChange?: any;
}

export default function OptionsPanel(props: OptionsPanelProps) {
  const [open, setOpen] = useState(false);

  return <>
    <IconButton onClick={() => setOpen(true)} icon={<SparkSettingLine />} bordered={false} />
    <Drawer
      destroyOnHidden
      open={open}
      onClose={() => setOpen(false)}
      styles={{ body: { padding: 0 }, header: { padding: 8 } }}>
      <OptionsEditor value={props.value} onChange={(v: typeof props.value) => {
        setOpen(false);
        props.onChange(v);
      }} />
    </Drawer>
  </>
}