import './Button.css'

export function Button({ 
  children, 
  variant = 'primary', 
  size = 'md',
  className = '',
  disabled = false,
  type = 'button',
  ...props 
}) {
  const classes = `btn btn-${variant} btn-${size} ${className}`.trim()
  
  return (
    <button 
      className={classes}
      disabled={disabled}
      type={type}
      {...props}
    >
      {children}
    </button>
  )
}

