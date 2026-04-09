from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('base', '0002_add_some_view'),  # your last migration
    ]

    operations = [
        # ------------------ user table ------------------
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS idx_user_name ON user(User_Name);
                CREATE INDEX IF NOT EXISTS idx_user_email ON user(User_Email);
                CREATE INDEX IF NOT EXISTS idx_user_lastname ON user(User_LN);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_user_name;
                DROP INDEX IF EXISTS idx_user_email;
                DROP INDEX IF EXISTS idx_user_lastname;
            """
        ),

        # ------------------ project table ------------------
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS idx_project_name ON project(Project_Name);
                CREATE INDEX IF NOT EXISTS idx_project_customer ON project(Customer_ID_id);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_project_name;
                DROP INDEX IF EXISTS idx_project_customer;
            """
        ),

        # ------------------ project_user table ------------------
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS idx_projectuser_project ON project_user(Project_ID_id);
                CREATE INDEX IF NOT EXISTS idx_projectuser_user ON project_user(User_ID_id);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_projectuser_project;
                DROP INDEX IF EXISTS idx_projectuser_user;
            """
        ),

        # ------------------ media table ------------------
        migrations.RunSQL(
            sql="""
                CREATE INDEX IF NOT EXISTS idx_media_filename ON media(File_Name);
                CREATE INDEX IF NOT EXISTS idx_media_filepath ON media(File_Path);
                CREATE INDEX IF NOT EXISTS idx_media_project ON media(Project_ID_id);
            """,
            reverse_sql="""
                DROP INDEX IF EXISTS idx_media_filename;
                DROP INDEX IF EXISTS idx_media_filepath;
                DROP INDEX IF EXISTS idx_media_project;
            """
        ),
    ]