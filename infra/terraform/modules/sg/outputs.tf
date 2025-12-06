output "alb_sg_id" {
  value = aws_security_group.alb.id
}

output "ecs_service_sg_id" {
  value = aws_security_group.ecs_service.id
}

output "internal_sg_id" {
  value = aws_security_group.internal.id
}
