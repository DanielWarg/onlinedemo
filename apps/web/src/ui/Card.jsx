import './Card.css'

export function Card({ 
  children, 
  className = '',
  onClick,
  interactive = false,
  ...props 
}) {
  const classes = `card ${interactive ? 'card-interactive' : ''} ${className}`.trim()
  
  return (
    <div 
      className={classes}
      onClick={onClick}
      {...props}
    >
      {children}
    </div>
  )
}

