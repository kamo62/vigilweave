import { cva, type VariantProps } from 'class-variance-authority'
import type { LucideIcon } from 'lucide-react'
import { type HTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-sm px-2.5 py-0.5 text-xs font-semibold transition-colors gap-1',
  {
    variants: {
      variant: {
        default: 'border border-transparent',
        flat: 'border border-transparent',
        bordered: 'border',
        dot: 'border border-transparent pl-3.5 relative before:absolute before:left-1.5 before:top-1/2 before:-translate-y-1/2 before:h-1.5 before:w-1.5 before:rounded-full',
      },
      color: {
        default: '',
        primary: '',
        success: '',
        warning: '',
        danger: '',
      },
      size: {
        sm: 'px-2 py-0.5 text-[10px]',
        md: 'px-2.5 py-0.5 text-xs',
        lg: 'px-3 py-1 text-sm',
      },
    },
    compoundVariants: [
      // flat
      { variant: 'flat', color: 'default', className: 'bg-muted text-muted-foreground' },
      { variant: 'flat', color: 'primary', className: 'bg-primary/10 text-primary' },
      { variant: 'flat', color: 'success', className: 'bg-success/15 text-success' },
      { variant: 'flat', color: 'warning', className: 'bg-warning/15 text-warning' },
      { variant: 'flat', color: 'danger', className: 'bg-danger/15 text-danger' },
      // default (solid)
      { variant: 'default', color: 'default', className: 'bg-secondary text-secondary-foreground' },
      { variant: 'default', color: 'primary', className: 'bg-primary text-primary-foreground' },
      { variant: 'default', color: 'success', className: 'bg-success text-success-foreground' },
      { variant: 'default', color: 'warning', className: 'bg-warning text-warning-foreground' },
      { variant: 'default', color: 'danger', className: 'bg-destructive text-destructive-foreground' },
      // bordered
      { variant: 'bordered', color: 'default', className: 'border-border text-muted-foreground' },
      { variant: 'bordered', color: 'primary', className: 'border-primary/30 text-primary' },
      { variant: 'bordered', color: 'success', className: 'border-success/30 text-success' },
      { variant: 'bordered', color: 'warning', className: 'border-warning/30 text-warning' },
      { variant: 'bordered', color: 'danger', className: 'border-danger/30 text-danger' },
      // dot
      { variant: 'dot', color: 'default', className: 'bg-muted text-muted-foreground before:bg-muted-foreground' },
      { variant: 'dot', color: 'primary', className: 'bg-primary/10 text-primary before:bg-primary' },
      { variant: 'dot', color: 'success', className: 'bg-success/10 text-success before:bg-success' },
      { variant: 'dot', color: 'warning', className: 'bg-warning/10 text-warning before:bg-warning' },
      { variant: 'dot', color: 'danger', className: 'bg-danger/10 text-danger before:bg-danger' },
    ],
    defaultVariants: {
      variant: 'flat',
      color: 'default',
      size: 'sm',
    },
  },
)

type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants> & {
  icon?: LucideIcon
}

function Badge({ className, variant, color, size, icon: Icon, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant, color, size, className }))} {...props}>
      {Icon && <Icon className="h-3 w-3" />}
      {children}
    </span>
  )
}

export { Badge }
