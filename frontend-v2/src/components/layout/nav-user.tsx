import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'

export function NavUser() {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton size='lg' className='cursor-default'>
          <Avatar className='size-8 rounded-lg'>
            <AvatarFallback className='rounded-lg bg-primary/20 text-xs font-semibold text-primary'>
              AG
            </AvatarFallback>
          </Avatar>
          <div className='grid flex-1 text-start text-sm leading-tight'>
            <span className='truncate font-semibold'>Agent · Office 30</span>
            <span className='truncate text-xs text-muted-foreground'>
              Demo role: risk officer
            </span>
          </div>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
