import './Input.css'

export function Input({ 
  className = '',
  ...props 
}) {
  const classes = `input ${className}`.trim()
  
  return (
    <input 
      className={classes}
      {...props}
    />
  )
}

export function Textarea({ 
  className = '',
  ...props 
}) {
  const classes = `input textarea ${className}`.trim()
  
  return (
    <textarea 
      className={classes}
      {...props}
    />
  )
}

