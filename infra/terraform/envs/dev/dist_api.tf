#infra/terraform/envs/dev/dist_api.tf
module "dist_api_service" {
  source = "../../modules/ecs_service"

  service_name = "dist-api"

  cluster_arn = module.ecs_cluster.cluster_arn
  vpc_id      = module.vpc.vpc_id

  private_subnet_ids = module.vpc.private_subnet_ids
  public_subnet_ids  = module.vpc.public_subnet_ids

  security_group_ids    = [module.sg.ecs_service_sg_id]
  alb_security_group_id = module.sg.alb_sg_id

  container_image = "${module.ecr.repository_urls["dist-api"]}:latest"
  container_port  = 8001

  task_cpu    = 512
  task_memory = 1024

  desired_count    = 1
  health_check_path = "/health"

  environment_variables = {
  # --- Redis (TEMP PLACEHOLDER) ---
  REDIS_HOST          = module.redis.redis_endpoint
  REDIS_PORT          = "6379"
  REDIS_DB            = "0"

  # --- Environment Name ---
  ENVIRONMENT         = var.environment
  }

  tags = local.tags
}
