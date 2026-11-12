import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { Loader2 } from 'lucide-react'
import { type ButtonHTMLAttributes, forwardRef } from 'react'

import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground shadow-sm hover:bg-primary/90',
        destructive: 'bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90',
        outline: 'border border-input bg-transparent hover:bg-accent hover:text-accent-foreground',
        secondary: 'bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        link: 'text-primary underline-offset-4 hover:underline',
        flat: 'bg-muted text-foreground hover:bg-accent',
        light: 'text-muted-foreground hover:bg-muted hover:text-foreground',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-8 rounded-sm px-3 text-xs',
        lg: 'h-12 rounded-sm px-8',
        icon: 'h-10 w-10',
      },
      color: {
        default: '',
        primary: '',
        danger: '',
      },
    },
    compoundVariants: [
      { variant: 'default', color: 'primary', className: 'bg-primary text-primary-foreground hover:bg-primary/90' },
      { variant: 'default', color: 'danger', className: 'bg-destructive text-destructive-foreground hover:bg-destructive/90' },
      { variant: 'flat', color: 'primary', className: 'bg-primary/10 text-primary hover:bg-primary/20' },
      { variant: 'flat', color: 'danger', className: 'bg-destructive/10 text-destructive hover:bg-destructive/20' },
    ],
    defaultVariants: {
      variant: 'default',
      size: 'default',
      color: 'default',
    },
  },
)

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
    isLoading?: boolean
    isDisabled?: boolean
    isIconOnly?: boolean
  }

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, color, asChild = false, isLoading, isDisabled, isIconOnly, children, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size: isIconOnly ? 'icon' : size, color, className }))}
        disabled={isDisabled || isLoading || props.disabled}
        ref={ref}
        {...props}
      >
        {asChild ? (
          children
        ) : (
          <>
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {children}
          </>
        )}
      </Comp>
    )
  },
)
Button.displayName = 'Button'

export { Button }
