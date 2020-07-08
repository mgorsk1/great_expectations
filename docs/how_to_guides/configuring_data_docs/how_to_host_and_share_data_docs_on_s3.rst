.. _how_to_guides__configuring_data_docs__how_to_host_and_share_data_docs_on_s3:

How to host and share Data Docs on S3
=====================================

By default, Data Docs are stored in HTML format in the ``data_docs/local_site/`` subdirectory of your ``great_expectations/uncommitted/`` folder.  This guide will help you configure Great Expectations to store them in a Amazon Web Services S3 (AWS S3) bucket so that they can be easily shared with your team.

.. admonition:: Prerequisites: This how-to guide assumes that you have already:

    - Configured a :ref:`Data Context <tutorials__getting_started__initialize_a_data_context>`.
    - Configured an :ref:`Expectations Suite <tutorials__getting_started__create_your_first_expectations>`.
    - Installed `boto3 <https://github.com/boto/boto3>`_ in your local environment.
    - Identified the S3 bucket and prefix where Expectations will be stored.


Steps
-----

1. **Configure** `boto3 <https://github.com/boto/boto3>`_ **to connect to the Amazon S3 bucket where Expectations will be stored.**

    Instructions on how to set up `boto3 <https://github.com/boto/boto3>`_ with AWS can be found at boto3's `documentation site <https://boto3.amazonaws.com/v1/documentation/api/latest/index.html>`_.


2. **Identify your Data Context Data Docs Sites**

    In your ``great_expectations.yml``, look for the following lines (comments removed in the snippet below).  This default configuration tells Great Expectations to build the ``local_site`` using the ``SiteBuilder`` and store in your filesystem in the ``store_backend.base_directory``.

    .. code-block:: yaml
        data_docs_sites:
            local_site:
                class_name: SiteBuilder
                show_how_to_buttons: true
                store_backend:
                    class_name: TupleFilesystemStoreBackend
                    base_directory: uncommitted/data_docs/local_site/
                site_index_builder:
                    class_name: DefaultSiteIndexBuilder


3. **Update your configuration file to include a new Data Doc site on S3.**

    In our case, the name is set to ``S3_site``, but it can be any name you like.  We also need to make some changes to the ``store_backend`` settings.  The ``class_name`` will be set to ``TupleS3StoreBackend``, ``bucket`` will be set to the address of your S3 bucket, and an optional ``prefix`` will be set to the folder where Data Docs files will be located.

    .. warning::
        If you are also storing :ref:`Validations in S3 <how_to_guides__configuring_metadata_stores__how_to_configure_a_validation_result_store_in_s3>` or `Expectations in S3 <how_to_guides__configuring_metadata_stores__how_to_configure_an_expectation_store_in_amazon_s3>`, please ensure that the ``prefix`` values are disjoint and one is not a substring of the other.

    .. code-block:: yaml

        expectations_store_name: expectations_S3_store

        stores:
            expectations_S3_store:
                class_name: ExpectationsStore
                store_backend:
                    class_name: TupleS3StoreBackend
                    bucket: '<your_s3_bucket_name>'
                    prefix: '<your_s3_bucket_folder_name>'

.. discourse::
   :topic_identifier: 233
