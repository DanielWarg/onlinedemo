import './Select.css'

export function Select({ 
  children,
  className = '',
  ...props 
}) {
  const classes = `select ${className}`.trim()
  
  return (
    <select 
      className={classes}
      {...props}
    >
      {children}
    </select>
  )
}

