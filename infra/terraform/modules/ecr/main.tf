resource "aws_ecr_repository" "this" {
  for_each = toset(var.repository_names)

  name = each.value

  image_scanning_configuration {
    scan_on_push = true
  }

  image_tag_mutability = "MUTABLE"

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(
    var.tags,
    {
      "Name" = each.value
    }
  )
}
