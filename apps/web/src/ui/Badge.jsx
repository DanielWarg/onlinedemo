import './Badge.css'

export function Badge({ 
  children, 
  variant = 'default',
  className = '',
  ...props 
}) {
  const classes = `badge badge-${variant} ${className}`.trim()
  
  return (
    <span className={classes} {...props}>
      {children}
    </span>
  )
}

