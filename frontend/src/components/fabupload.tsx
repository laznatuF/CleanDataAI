type Props={ onClick:()=>void, title?:string }
export function FabUpload({onClick, title="Subir archivo"}:Props){
  return <button className="fab-upload" aria-label={title} title={title} onClick={onClick}>↑</button>;
}
