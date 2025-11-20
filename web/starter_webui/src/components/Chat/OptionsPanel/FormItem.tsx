import { Form } from 'antd';
import { createStyles } from 'antd-style';


interface FormItemProps {
  name: string | string[];
  label: string;
  isList?: boolean;
  children: any;
  normalize?: (value: any) => any;
}


const useStyles = createStyles(({ token }) => ({
  label: {
    marginBottom: 6,
    fontSize: 12,
    color: token.colorTextSecondary,
  },

}));

export default function FormItem(props: FormItemProps) {
  const { styles } = useStyles();


  const node = props.isList ?
    <Form.List name={props.name}>{props.children}</Form.List> :
    <Form.Item name={props.name} normalize={props.normalize}>{props.children}</Form.Item>;


  return <div>
    {props.label && <div className={styles.label}>{props.label}</div>}
    {node}
  </div>

}